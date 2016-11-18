"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import json
import logging
import requests
import random

from django.db import transaction
from django.conf import settings
import django.utils.timezone

from ccm.common import crdt, delta
from endagaweb.models import BillingTier
from endagaweb.models import ClientRelease
from endagaweb.models import ConfigurationKey
from endagaweb.models import Destination
from endagaweb.models import Subscriber
from endagaweb.models import TimeseriesStat
from endagaweb.models import UsageEvent
from endagaweb.util.parse_destination import parse_destination


class CheckinResponder(object):

    # optimizers is a class level object that is used to retain optimizer
    # state for each BTS across multiple instances of this class (which are
    # newly created on each BTS checkin).
    optimizers = delta.DeltaProtocolOptimizerFactory()

    def __init__(self, bts):
        """
        Instance of this class is newly created each time a BTS sends a
        checkin request to the server. At the end of handling that request
        this instance is discarded, but the optimizer state is retained in
        the class-level optimizers object (see above).
        """
        self.bts = bts
        self._bts_ctx_sections = {}
        # these are handlers for individual fields sent by the BTS on checkin
        self.handlers = {
            delta.DeltaProtocol.CTX_KEY: self.delta_handler,
            'usage': self.usage,
            'versions': self.versions,
            'camped_subscribers': self.camped_subscribers,
            'uptime': self.uptime,
            'openbts_load': self.timeseries_handler,
            'openbts_noise': self.timeseries_handler,
            'system_utilization': self.timeseries_handler,
            'subscribers': self.subscribers_handler,
            'radio': self.radio_handler,  # needs location_handler -kurtis
            # TODO: (kheimerl) T13270418 Add location update information
        }

    # Delta optimization CTX handler
    def delta_handler(self, delta_ctx):
        """
        Verifies client's provided CTX and saves it in this instance for
        subsequent use by _optimize.

        Args:
            delta_ctx: Client CTX sent with delta.DeltaProtocol.CTX_KEY key
        """
        self._bts_ctx_sections.clear()
        if isinstance(delta_ctx, dict) and len(delta_ctx) == 1:
            sections = delta_ctx.get(
                delta.DeltaProtocolOptimizer.SECTIONS_CTX_KEY
            )
            if sections and isinstance(sections, dict):
                for section, data in sections.items():
                    logging.info(
                        "got delta section '%s' from BTS %s: %s" %
                        (section, self.bts.uuid, data))
                    self._bts_ctx_sections[section] = data
            else:
                logging.info(
                    'Missing Delta CTX sections. BTS: %s' % self.bts.uuid)
        else:
            logging.info('Unrecognized Delta CTX from BTS: %s' % self.bts.uuid)

    # Delta optimization wrapper
    def _optimize(self, section_name, section_data):
        """
        Delta optimization wrapper. Takes optimized section name and original
        data, finds or creates BTS ID & section specific optimizer and tries
        to calculate delta if the optimizer has prior CTX and it matches CTX
        provided by the client (BTS)
        Args:
            section_name: optimized section name
            section_data: original data/config dictionary

        Returns: either optimized delta or original data

        """
        if not self.bts.uuid:
            # when is this not true?
            logging.error("No UUID for BTS")
            return section_data

        dict_ctx = self._bts_ctx_sections.get(section_name)
        # if BTS sent us a delta context for this section:
        if dict_ctx:
            # extract the delta protocol data from the received context
            client_ctx = delta.DeltaProtocolCtx.create_from_dict(dict_ctx)

            # get the existing optimizer state for this BTS-section
            bts_sect_id = self.bts.uuid + '&' + section_name
            optimizer = CheckinResponder.optimizers.get(bts_sect_id)

            # there may be no delta context for this BTS, if either the
            # server was restarted or its a new BTS. If the server was
            # restarted but the contents of a section don't change, the
            # context sent by the client should still match section_data
            # and the server can send an empty delta.
            if not optimizer.ctx:
                logging.info("No server context for '%s', BTS %s" %
                             (section_name, self.bts.uuid))
            else:
                if not client_ctx.compare(optimizer.ctx):
                    logging.warn(
                        "Signatures mismatch: expected %s, got %s. "
                        "(Section '%s', BTS: %s)" %
                        (optimizer.ctx.sig, client_ctx.sig,
                         section_name, self.bts.uuid))

            # Always return result of optimizer.prepare if client sent CTX
            # (client supports delta protocol), prepare will add server CTX
            # for next round even if it cannot create delta for current one
            section_data = optimizer.prepare(client_ctx, section_data)
        else:
            # Log missing CTX, most likely because BTS restarted and has no
            # CTX to send (but possibly BTS is running old software). Note
            # that in this case we don't automatically create server-side
            # optimizer(s) in case the client doesn't support optimization.
            logging.warn('Missing Delta CTX for section: %s, BTS: %s' %
                         (section_name, self.bts.uuid))
        return section_data

    def process(self, status):
        """
        Process a checkin from a BTS, and return the response dictionary.

        Status must be a decoded dictionary, and should be verified elsewhere
        to have come from the BTS.  This creates a response consisting of
        config parameters.
        """
        resp = {'status': 'fail'}
        self.bts.mark_active()
        for section in status:
            if section in self.handlers:
                self.handlers[section](status[section])

        resp['status'] = 'ok'
        resp['config'] = self._optimize('config', self.gen_config())
        resp['subscribers'] = self._optimize('subscribers',
                                             self.gen_subscribers())
        resp['events'] = self.gen_events()
        resp['sas'] = self.gen_spectrum()
        self.bts.save()
        return resp

    def usage(self, section):
        """Handles the usage section of a checkin.

        This currently just consists of an "events" subsection, which is a list
        of usage events.
        """
        resp = {}
        if "events" in section:
            events = section['events']
            destinations = list(Destination.objects.all())
            for event in events:
                resp['seqno'] = handle_event(self.bts, event, destinations)
        return resp

    def versions(self, section):
        versions = {}
        versions['endaga_version'] = self.bts.sortable_version(section['endaga'])
        versions['freeswitch_version'] = self.bts.sortable_version(section['freeswitch'])
        versions['python_endaga_core_version'] = self.bts.sortable_version(section['python-endaga-core'])
        # backwards compatibility
        if 'python-gsm' in section:
            versions['python_gsm_version'] = self.bts.sortable_version(section['python-gsm'])
        else:
            versions['python_gsm_version'] = self.bts.sortable_version(section['python-openbts'])
        if 'gsm' in section:
            versions['gsm_version'] = self.bts.sortable_version(section['gsm'])
        else:
            versions['gsm_version'] = self.bts.sortable_version(section['openbts-public'])
        self.bts.package_versions = json.dumps(versions)

    def camped_subscribers(self, camped_subscribers):
        """Handles the subscribers updates in a checkin.

        These checkins consist of a list IMSI and sec_since_last_seen key pairs
        """
        for entry in camped_subscribers:
            try:
                sub = Subscriber.objects.get(imsi=entry['imsi'])
            except Subscriber.DoesNotExist:
                logging.info(
                    '[camped_subscribers] subscriber %s does not exist. '
                    'BTS: %s',
                    entry['imsi'], self.bts.uuid)
                continue

            # The last seen timestamp is a little erred since its computed
            # from the current time
            last_seen_datetime = self.bts.last_active - \
                datetime.timedelta(seconds=int(entry['last_seen_secs']))

            sub.mark_camped(last_seen_datetime, bts=self.bts)

            # Persist
            sub.save()

    def uptime(self, uptime):
        """
        Process the reported uptime of the BTS.
        """
        self.bts.uptime = uptime

    def timeseries_handler(self, section):
        """
        Save the TimeseriesStat values that are reported in various sections
        of the checkin. Multiple checkin sections can use this, and as long as
        they're all just a dictionary of key-value timeseries pairs they can be
        processed with this generic handler.
        """
        now = django.utils.timezone.now()
        for key in section.keys():
            with transaction.atomic():
                stat = TimeseriesStat(
                    key=key, value=section[key], date=now,
                    bts=self.bts, network=self.bts.network)
                stat.save()

    def subscribers_handler(self, subscribers):
        """
        Update the subscribers' balance info based on what the client submits.

        TODO(shasan): handle new numbers?
        """
        for imsi in subscribers:
            bal = subscribers[imsi]['balance']
            try:
                # comes in as JSON
                client_bal = crdt.PNCounter.from_json(bal)
            except ValueError:
                logging.error("Invalid balance! Skipping %s:%s" %
                              (imsi, bal))
                continue
            try:
                Subscriber.update_balance(imsi, client_bal)
            except Subscriber.DoesNotExist:
                logging.error("Subscriber %s doesn't exist, skipping!" %
                              (imsi, ))
                continue

    def radio_handler(self, radio):
        if 'band' in radio and 'c0' in radio:
            self.bts.update_band_and_channel(radio['band'], radio['c0'])

    def gen_subscribers(self):
        """
        Returns a list of active subscribers for a network, along with
        PN-counter for each sub containing last known balance.
        """
        res = {}
        for s in Subscriber.objects.filter(network=self.bts.network):
            bal = crdt.PNCounter.from_state(json.loads(s.crdt_balance))
            data = {'numbers': s.numbers_as_list(), 'balance': bal.state}
            res[s.imsi] = data
        return res

    def gen_config(self):
        """Create a checkinresponse with Network and BTS config settings.

        This section of the checkin response is contained by the "config" key
        and is of the form: {
            'endaga': {},       # Values for the client's ConfigDB like the
                                # number_country and legacy pricing data
            'openbts': {},      # OpenBTS config values
            'prices': {},       # billing tier data
            'autoupgrade': {},  # autoupgrade preferences
        }

        BillingTier data is sent to the BTS in the following form:
            {
                'directionality': 'off_network_send',
                'prefix': '53',
                'country_name': 'Finland',
                'country_code': 'FI',
                'cost_to_subscriber_per_sms': 5000,
                'cost_to_subscriber_per_min': 2000,
                'billable_unit': 1,
            }, {
                'directionality': 'off_network_receive',
                'cost_to_subscriber_per_sms': 200,
                'cost_to_subscriber_per_min': 100,
                'billable_unit': 1,
            }, {
                'directionality': 'on_network_send',
                'cost_to_subscriber_per_sms': 300,
                'cost_to_subscriber_per_min': 200,
                'billable_unit': 1,
            }, {
                'directionality': 'on_network_receive',
                'cost_to_subscriber_per_sms': 20,
                'cost_to_subscriber_per_min': 10,
                'billable_unit': 1,
            }

        There will naturally be many off_network_send elements -- one for each
        country we serve.
        """

        # Get all configuration relevant to this BTS and network.
        # Have BTS configs override network-wide configs by processing the
        # BTS-specific config set first and ignoring duplicates
        # as we generate the result.

        config_set = [
            ConfigurationKey.objects.filter(bts=self.bts).order_by('key'),
            ConfigurationKey.objects.filter(network=self.bts.network)
            .order_by('key')
        ]

        result = {}
        for config_set in config_set:
            for config in config_set:
                if config.category not in result:
                    result[config.category] = {}
                if config.key in result[config.category]:
                    continue  # ignore duplicates
                elif config.bts and config.bts != self.bts:
                    continue  # ignore keys that don't belong to this BTS
                else:
                    result[config.category][config.key] = config.value
        # Get all Destinations and all BillingTiers for the associated network.
        destinations = Destination.objects.all()
        tiers = BillingTier.objects.filter(network=self.bts.network)
        off_network_send_tiers = [t for t in tiers
                                  if t.directionality == 'off_network_send']
        pricing_data = []
        for destination in destinations:
            # Find the BillingTier which has the same DestinationGroup as this
            # Destination.
            for tier in off_network_send_tiers:
                if tier.destination_group != destination.destination_group:
                    continue
                pricing_data.append({
                    'directionality': tier.directionality,
                    'prefix': destination.prefix,
                    'country_name': destination.country_name,
                    'country_code': destination.country_code,
                    'cost_to_subscriber_per_sms': (
                        tier.cost_to_subscriber_per_sms),
                    'cost_to_subscriber_per_min': (
                        tier.cost_to_subscriber_per_min),
                    'billable_unit': tier.billable_unit,
                })
                break
        # Inject the tier data for off-network receive and on-network
        # send/receive tiers.
        for tier in tiers:
            if tier.directionality == 'off_network_send':
                continue
            pricing_data.append({
                'directionality': tier.directionality,
                'cost_to_subscriber_per_sms': tier.cost_to_subscriber_per_sms,
                'cost_to_subscriber_per_min': tier.cost_to_subscriber_per_min,
                'billable_unit': tier.billable_unit,
            })
        result['prices'] = pricing_data
        # Tack on the Network's number country.
        if 'endaga' not in result.keys():
            result['endaga'] = {}
        # The django-pylint plugin is confused below because we define the
        # Network ForeignKey by name (with quotes) instead of by reference.  So
        # we'll disable that check.
        # pylint: disable=no-member
        result['endaga']['number_country'] = self.bts.network.number_country
        result['endaga']['currency_code'] = self.bts.network.subscriber_currency
        # Get the latest versions available on each channel.
        latest_stable_version = ClientRelease.objects.filter(
            channel='stable').order_by('-date')[0].version
        latest_beta_version = ClientRelease.objects.filter(
            channel='beta').order_by('-date')[0].version
        # Send autoupgrade preferences.
        result['autoupgrade'] = {
            'enabled': self.bts.network.autoupgrade_enabled,
            'channel': self.bts.network.autoupgrade_channel,
            'in_window': self.bts.network.autoupgrade_in_window,
            'window_start': self.bts.network.autoupgrade_window_start,
            'latest_stable_version': latest_stable_version,
            'latest_beta_version': latest_beta_version,
        }
        return result

    def gen_events(self):
        """
        Returns the events section, currently just a max_seqno
        """
        return {'seqno': self.bts.max_seqno}

    def gen_spectrum(self):
        """
        returns the spectrum allotment for this BTS
        """
        if not (settings.SASON_ACQUIRE_URL and settings.SASON_REQUEST_URL):
            return {'ok': False}

        def sas_acquire(band, chnl, pwr_lvl):
            try:
                return requests.post(settings.SASON_ACQUIRE_URL,
                                     {'uuid': self.bts.uuid,
                                      'lat': self.bts.latitude,
                                      'long': self.bts.longitude,
                                      'band': band,
                                      'channel': chnl,
                                      'power_level': pwr_lvl,
                })
            except Exception:
                logging.error('SASON Acquire failed')
                return None

        def sas_request():
            try:
                return requests.post(settings.SASON_REQUEST_URL,
                                     {'uuid': self.bts.uuid,
                                      'lat': self.bts.latitude,
                                      'long': self.bts.longitude,
                                      # self for now -kurtis
                                      'bands': self.bts.band,
                })
            except Exception:
                logging.error('SASON Request failed')
                return None

        if (self.bts.band):  # if we know the band
            # fenceposting
            # request the current band/channel.
            band = self.bts.band
            channel = self.bts.channel
            pwr_level = 100  # not yet stored in db, so guess
            # until we find a good channel
            tries_left = settings.SASON_RETRY_COUNT
            acq = sas_acquire(band, channel, pwr_level)
            while (acq is not None and
                   acq.status_code != requests.codes.ok and
                   tries_left > 0):
                tries_left -= 1
                # get the list of available ones
                req = sas_request()
                if (req is None or
                    req.status_code != requests.codes.ok):  # trouble
                    break
                # ask for it
                req = req.json()
                channel = random.choice(req[band])
                pwr_level = req['power_level']
                acq = sas_acquire(band, channel, pwr_level)
            # if we got one, return it
            if (acq is not None and
                acq.status_code == requests.codes.ok):
                # this is interesting
                # sason does the band and channel update already
                # so technically this is redundant
                # however we can't *assume* future SAS solutions will update
                # our database so we should do the update anyhow.
                self.bts.update_band_and_channel(band=band, channel=channel)
                return {
                    'ok': True,
                    'band': self.bts.band,  # use updated
                    'channel': self.bts.channel,  # use updated
                    'power_level': pwr_level,
                }
        return {'ok': False}


def handle_event(bts, event, destinations=None):
    """Handles a usage event from a BTS.

    Nothing happens if the event has a lower seqno than the max we've seen
    already (it gets ignored).  Otherwise, we create the UsageEvent, and
    associate it with the relevant subscriber.  Also updates the BTS' max
    seqno if we see a new one.

    Args:
      event: a usage event from the BTS (dict)
      destinations: ???

    Returns:
      the max_seqno
    """
    if event['seq'] <= bts.max_seqno:
        logging.warn("ignoring event (%d) from BTS %s" %
                     (event['seq'], bts.uuid))
        return bts.max_seqno
    try:
        sub = Subscriber.objects.get(imsi=event['imsi'])
    except Subscriber.DoesNotExist:
        logging.warn('[handle_event] subscriber %s does not exist.  BTS: %s' %
                     (event['imsi'], bts.uuid))
        return bts.max_seqno
    date = datetime.datetime.strptime(event['date'], '%Y-%m-%d %H:%M:%S')
    # Note that the default timezone should be UTC, no matter what the
    # UserProfile timezone settings are.
    date = django.utils.timezone.make_aware(
        date, django.utils.timezone.get_default_timezone())
    usage_event = UsageEvent(
        date=date, kind=event['kind'], oldamt=event['oldamt'],
        newamt=event['newamt'], change=event['change'],
        reason=event['reason'][:500], subscriber=sub, bts=bts)
    # Try to get a valid call duration.  This either comes from the
    # 'call_duration' key in new events or can be parsed from the reason.
    # If we can't figure it out, just set the default to zero from None.
    # (None is used if the usage event was not a call.)
    duration = None
    if 'sec call' in event['reason'][:500]:
        try:
            duration = int(event['reason'][:500].split()[0])
        except Exception:
            duration = 0
    usage_event.call_duration = event.get('call_duration', duration)
    usage_event.billsec = event.get('billsec', duration)
    usage_event.from_imsi = event.get('from_imsi')
    usage_event.from_number = event.get('from_number')
    usage_event.to_imsi = event.get('to_imsi')
    # Set the to_number and, if there is a to_number, set the Destination.
    usage_event.to_number = event.get('to_number')
    if event.get('to_number', None):
        if not destinations:
            destinations = list(Destination.objects.all())
        usage_event.destination = parse_destination(
            event.get('to_number'), destinations)
    usage_event.tariff = event.get('tariff')
    usage_event.uploaded_bytes = event.get('up_bytes')
    usage_event.downloaded_bytes = event.get('down_bytes')
    usage_event.timespan = event.get('timespan')
    # balance is updated in the subscribers_handler above -kurtis
    bts.max_seqno = event['seq']
    # Bill the operator for local traffic.  Billing for voice occurs in the
    # internal API, and billing for outgoing and incoming SMS occurs near
    # calls to the Nexmo API.
    receive_kinds = ('local_recv_call', 'local_recv_sms')
    send_kinds = ('local_call', 'local_sms')
    if event['kind'] in receive_kinds + send_kinds:
        # The django-pylint plugin is confused below because we define the
        # Network ForeignKey by name (with quotes) instead of by reference.
        # So we'll disable that check.
        # pylint: disable=no-member
        if event['kind'] in receive_kinds:
            directionality = 'on_network_receive'
        elif event['kind'] in send_kinds:
            directionality = 'on_network_send'
        if 'sms' in event['kind']:
            cost = bts.network.calculate_operator_cost(
                directionality, 'sms')
            bts.network.bill_for_sms(cost, event['kind'])
        elif 'call' in event['kind']:
            billable_seconds = int(event.get('billsec', duration))
            cost = bts.network.calculate_operator_cost(
                directionality, 'call')
            bts.network.bill_for_call(cost, billable_seconds,
                                       event['kind'])
    # Persist.
    usage_event.save()
    sub.save()
    bts.save()
    return bts.max_seqno
