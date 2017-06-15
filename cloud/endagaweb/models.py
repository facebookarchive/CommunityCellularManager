"""Models for the endagaweb django app.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import calendar
import datetime
import json
import logging
import time
import uuid

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.gis.db import models as geomodels
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import connection
from django.db import models
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from guardian.shortcuts import (assign_perm, get_users_with_perms)
from rest_framework.authtoken.models import Token
import django.utils.timezone
import itsdangerous
import pytz
import stripe

from ccm.common import crdt, logger
from ccm.common.currency import humanize_credits, CURRENCIES
from endagaweb.billing import tier_setup
from endagaweb.celery import app as celery_app
from endagaweb.notifications import bts_up
from endagaweb.util import currency as util_currency
from endagaweb.util import dbutils as dbutils

stripe.api_key = settings.STRIPE_API_KEY


# These UsageEvent kinds do not count towards subscriber activity.
NON_ACTIVITIES = (
    'deactivate_number', 'deactivate_subscriber', 'add_money',
    'deduct_money', 'set_balance', 'unknown',
)
# These UsageEvent kinds count towards outbound activity.  This is the type of
# activity that determines whether to deactivate an "idle" subscriber.
OUTBOUND_ACTIVITIES = (
    'outside_call', 'outside_sms', 'local_call', 'local_sms',
)


class UserProfile(models.Model):
    """UserProfiles extend the default Django User models.

    Info that is custom to our app is added here.  Users are primarily used for
    auth, while everything else uses UserProfiles.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    timezone_choices = [(v, v) for v in pytz.common_timezones]
    timezone = models.CharField(max_length=50, default='UTC',
                                choices=timezone_choices)

    # A UI kludge indicate which network a user is currently viewing
    # Important: This is not the only network a User is associated with
    # because a user may have permissions on other Network instances.
    # For example to get a list of networks the user can view:
    # >>> get_objects_for_user(user_profile.user, 'view_network', klass=Network)
    network = models.ForeignKey('Network', null=True, on_delete=models.SET_NULL)

    def __str__(self):
          return "%s's profile" % self.user

    def display_name(self):
        if self.user.get_short_name():
            return self.user.get_short_name()
        else:
            return self.user.username

    def alerts(self):
        """Surfaces alerts associated with this user profile (e.g., BTS down).

        TODO(matt): implement
        """
        #return [{'link': "#", 'title': "lookout!", 'label': "Danger"}]

    @staticmethod
    def new_user_hook(sender, instance, created, **kwargs):
        """
        A User post_save hook that creates a new user Profile, Network,
        and if the User was just created.
        """
        if created and instance.username != settings.ANONYMOUS_USER_NAME:
            profile = UserProfile.objects.create(user=instance)
            network = Network.objects.create()
            network.auth_group.user_set.add(instance)
            network.save()
            # Make this the users currently selected network
            profile.network = network
            profile.save()

post_save.connect(UserProfile.new_user_hook, sender=User)

class Ledger(models.Model):
    """A ledger represents a list of transactions and a balance.

    Attributes:
        network: a network associated with the ledger
        balance: the account balance -- updated after every transaction
    """
    network = models.OneToOneField('Network',
                                   related_name="ledger",
                                   null=True,
                                   on_delete=models.CASCADE)
    balance = models.BigIntegerField(default=0)

    def __unicode__(self):
        name = self.network.name if self.network else '<None>'
        return "Ledger: network %s, current balance %s (millicents)" % (
            name, self.balance)

    def add_transaction(self, kind, amount, reason):
        """ Create a new transaction, save it. """
        if self.network.billing_enabled:
            Transaction.new(ledger=self,
                            amount=amount,
                            kind=kind,
                            reason=reason).save()

    @staticmethod
    def transaction_save_handler(sender, instance, created, **kwargs):
        """Updates the Ledger balance after a transaction is saved.

        Args:
            instance: a Transaction instance
        """
        if not created:
            raise ValueError("Transactions should not be modified")

        # Atomically update the ledger's balance.
        with transaction.atomic():
            ledger = (Ledger.objects.select_for_update()
                      .get(id=instance.ledger.id))
            # check if billing is enabled
            if not ledger.network.billing_enabled:
                # Transaction creator should have checked before saving,
                # issue a warning
                logger.with_trace(
                    logger.warning,
                    "creator should check if billing is enabled"
                )
                return
            ledger.balance = F('balance') + instance.amount
            ledger.save()

class Transaction(models.Model):
    """ The transaction object represents a single line item in an account
    ledger.  It needs to be applied to a ledger for it to take affect. In
    general, you shouldn't set an amount (it'll be determined automatically by
    the biller associated with whatever ledger this is applied to).

    Attributes:
      created: when this Transaction was instantiated
      ledger: a link to a Ledger instance
      count: the number of instances of this transaction.  Mostly used to bill
             voice in minutes.
      amount: value of the transaction in millicents (1/1000 of a cent)
      kind: the type of transaction.  When operators are granted credits via a
            CC recharge, that is a 'credit' kind of transaction.  We charge
            credits for the monthly use of numbers or for the network's
            subscribers making and receiving SMS and calls.  These come from
            event kinds which are defined in the client repo.
      reason: freeform notes as to why this transaction happened (free SMS or
              added credit from UI, refunding billing error, etc)
    """
    created = models.DateTimeField(default=django.utils.timezone.now)
    ledger = models.ForeignKey(Ledger, null=True, on_delete=models.CASCADE)
    count = models.IntegerField(default=1)
    amount = models.BigIntegerField(default=0)

    transaction_kinds = (
        ('credit', 'credit'),
        ('outside_sms', 'outside_sms'),
        ('outside_call', 'outside_call'),
        ('incoming_sms', 'incoming_sms'),
        ('incoming_call', 'incoming_call'),
        ('local_sms', 'local_sms'),
        ('local_call', 'local_call'),
        ('local_recv_call', 'local_recv_call'),
        ('local_recv_sms', 'local_recv_sms'),
        ('number.nexmo.monthly', 'number.nexmo.monthly'),
    )
    kind = models.CharField(max_length=100, choices=transaction_kinds)
    reason = models.CharField(max_length=500)

    def __unicode__(self):
        return "Transaction(%s, %d, %d, %s, %s)" % (
            self.created, self.amount, self.count, self.kind, self.reason)

    def pretty_amount(self):
        """The idea is to use a method like this to localize the currency."""
        return self.amount

    @classmethod
    def new(cls, kind, **kwargs):
        """ Create a new Transaction, save it. """
        if kind not in [k for k, _ in cls.transaction_kinds]:
            raise ValueError("invalid transaction kind: '%s'" % (kind, ))
        return Transaction(kind=kind, **kwargs)


# Update the ledger balance after saving a transaction
post_save.connect(Ledger.transaction_save_handler, sender=Transaction)


class BTS(models.Model):
    """Model for our base stations."""
    network = models.ForeignKey('Network', on_delete=models.CASCADE)
    uuid = models.CharField(max_length=255, unique=True)
    # Callback URL for inbound requests. Right now, we require this to follow
    # RFC 1808 (i.e., start with a <protocol>://...). We should update this in
    # the future to only specify domain name/IP address and port.
    inbound_url = models.CharField(max_length=1024, null=True, blank=True)
    # Human-readable name.
    nickname = models.CharField(max_length=1024, null=True, blank=True)
    # The UsageEvent sequence number.
    # XXX: maybe should be a function that searches through events to find
    #      highest the seqno?
    max_seqno = models.IntegerField(default=0)
    # The last time this BTS was "active": checkin, contacted by cloud, etc
    last_active = models.DateTimeField(null=True, blank=True)
    # Whether the BTS has timed out or not
    status_choices = [
        ('no-data', 'No Data'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ]
    status = models.CharField(
        max_length=20, choices=status_choices, default='no-data')
    # BTS registration
    registration_choices = [
        ('registered', 'Registered'),
        ('unregistered', 'Unregistered'),
        ('disabled', 'Disabled')
    ]
    registration_status = models.CharField(
        max_length=20, choices=registration_choices, default='unregistered')
    certificate = models.TextField(null=True)
    secret = models.TextField(null=True)
    # Package version data as reported by the BTS itself.  We'll store the
    # versions themselves as zero-padded strings to fix sorting issues
    # (e.g. version '2.0.0' naturally sorts higher than '10.0.0').  The version
    # numbers will look like '00001.00002.00003' -- see
    # stackoverflow.com/a/28208626/232638.  The data is JSON-encoded
    # with keys: endaga_version, freeswitch_version, gsm_version,
    # python_endaga_core_version and python_gsm_version.
    package_versions = models.TextField(null=True)
    # Towers report their uptime in seconds during checkins.
    uptime = models.IntegerField(null=True)
    #location of the tower, default is campanile
    #can't use point object for some reason
    location = geomodels.GeometryField(geography=True, default='POINT(-122.260931 37.871783)')
    #power level of the tower
    power_level = models.IntegerField(default=100)
    #band used - eventually can add more
    #authoritative place for range as well
    #name, dbname, acceptable ranges
    #maybe should be in config somewhere
    #null means no band set
    #only odd for GSM as bands overlap
    bands = {
        'GSM850' : {'choices' : ('GSM850', 'GSM850'),
                    "valid_values" : set(range(128,252,2))},
        'GSM900' : {'choices' : ('GSM900', 'GSM900'),
                    "valid_values" : set(range(0,125,1))},
        'GSM1800' : {'choices' : ('GSM1800', 'GSM1800'),
                     "valid_values" : set(range(512,886,2))},
        'GSM1900' : {'choices' : ('GSM1900', 'GSM1900'),
                     "valid_values" : set(range(512,811,2))}
    }

    band = models.CharField(
        max_length=20, choices=[bands[i]['choices'] for i in bands.keys()], null=True)
    #channel number used
    #none is unknown or invalid
    channel = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return "BTS(%s, %s, last active: %s)" % (
            self.uuid, self.inbound_url, self.last_active)

    #custom validations
    #this is run after every time an object is updated
    #authoritatively enforcing the DB values
    def clean(self):
        super(BTS, self).clean()
        if (self.band is None and self.channel is None):  # valid bad state
            return
        elif not self.valid_band_and_channel(self.band, self.channel):
            raise ValidationError({'channel': 'Invalid Channel or Band selected'})
        return

    def save(self, *args, **kwargs):
        self.clean()
        super(BTS, self).save(*args, **kwargs)

    def valid_band(self, band):
        return band in BTS.bands

    def valid_band_and_channel(self, band, channel):
        #null means channel is not set
        return (self.valid_band(band) and
                (channel in BTS.bands[band]['valid_values']))

    #use this to set band/channel as to never set to invalid
    def update_band_and_channel(self, band=None, channel=None):
        #can't use self.band as the default argument
        if not band:
            band = self.band
        if not channel:
            channel = self.channel

        channel = int(channel)
        if self.valid_band_and_channel(band, channel):
            self.band = band
            self.channel = channel
            return True
        else:
            logging.warn("Invalid band(%s) or channel(%s) selected" % (band, channel))
            self.band = None
            self.channel = None
            return False

    @property
    def latitude(self):
        return self.location.y

    @property
    def longitude(self):
        return self.location.x

    def is_registered(self):
        return self.registration_status == "registered"

    def needs_vpnconf(self):
        """Return true if the BTS should be able to request an API key and
        OpenSSL conf.

        Disabled BTS units should not be able to receive this, nor should
        already registered ones.
        """
        return self.registration_status == "unregistered"

    def mark_registered(self):
        self.registration_status = "registered"

    def mark_active(self):
        """Mark the BTS as active (only save during status transition)."""
        bts_up(self)
        self.last_active = django.utils.timezone.now()
        if self.status != 'active':
            self.status = 'active'
            self.save()
            up_event = SystemEvent(
                    date=django.utils.timezone.now(), bts=self,
                    type='bts up')
            up_event.save()

    def last_active_time(self):
        """Gets the last time the BTS was active.

        Returns:
            Last checkin time if there was one, otherwise None
        """
        if self.last_active:
            return self.last_active
        return None

    def generate_jwt(self, data_dict):
        """Generate a JSON web token for this BTS.

        IMPORTANT: This is subject to replay attacks if there's not a nonce in
        the JWT. It's the callers responsibility to include this in the data
        dict if replay attacks are a concern (a random, unique msgid would
        suffice).
        """
        serializer = itsdangerous.JSONWebSignatureSerializer(self.secret)
        return serializer.dumps(data_dict)

    def sortable_version(self, version):
        """Converts '1.2.3' into '00001.00002.00003'"""
        # Version must be a string to split it.
        version = str(version)
        return '.'.join(bit.zfill(5) for bit in version.split('.'))

    def printable_version(self, version):
        """Converts '00001.00002.00003' into '1.2.3'

        The inverse of sortable_version.
        """
        # Make sure the version is not null.
        if version is None:
            return None
        version = str(version)
        numbers = []
        for number in version.split('.'):
            try:
                # Try to remove any leading zeros.
                number = int(number)
            except ValueError:
                # "number" is not int-able.
                pass
            # Convert back to a string.
            numbers.append(str(number))
        return '.'.join(numbers)

    @staticmethod
    def set_default_versions(sender, instance=None, created=False, **kwargs):
        """Post-create hook to setup network default settings."""
        if not created:
            return
        bts = instance
        default_versions = {
            'endaga_version': None,
            'freeswitch_version': None,
            'gsm_version': None,
            'python_endaga_core_version': None,
            'python_gsm_version': None,
        }
        bts.package_versions = json.dumps(default_versions)
        bts.save()


post_save.connect(BTS.set_default_versions, sender=BTS)


"""
Base class for a thing that issues recurring charges, like a number.
"""
class ChargingEntity(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    last_charged = models.DateTimeField(null=True, blank=True)
    kind = models.CharField(max_length=100, null=True)
    valid_through = models.DateTimeField(null=True, blank=True)
    recharge_num = models.IntegerField(default=1)
    recharge_unit = models.CharField(max_length=100, default="month")

    """
    Return a new datetime incremented by the specified number of units, one of
    "day", "month", or "year".
    """
    def add_time(self, sourcedate, num, unit):
        if unit == "month":
            month = sourcedate.month - 1 + num
            year = sourcedate.year + (month // 12)  # floor
            month = month % 12 + 1
            day = min(sourcedate.day, calendar.monthrange(year, month)[1])
            tzinfo = getattr(sourcedate, 'tzinfo', None)
            return datetime.datetime(year, month, day,
                                     sourcedate.hour, sourcedate.minute, 0,
                                     tzinfo=tzinfo)
        elif unit == "day":
            return sourcedate + datetime.timedelta(days=num)
        elif unit == "year":
            return sourcedate + datetime.timedelta(days=num*365)

    """
    Charge for this recurring entity. This can be called any time, and will
    only generate a new charge if the entity has expired.
    """
    def charge(self, curr_date=None, reason="recharge"):
        if curr_date is None:
            curr_date = django.utils.timezone.now()
        if not self.valid_through:
            self.valid_through = curr_date
        if self.valid_through <= curr_date:
            # TODO(matt): charge for this entity
            self.last_charged = curr_date
            self.valid_through = self.add_time(
                self.valid_through, self.recharge_num, self.recharge_unit)
            self.save()

    """
    Clear out the entity's billing info. This does not change the entity type.

    Sets everything back to null or their default value.
    """
    def reset(self):
        self.last_charged = None
        self.valid_through = None
        self.recharge_num = None
        self.recharge_unit = None
        self.save()

    class Meta:
        abstract = True


class Subscriber(models.Model):
    network = models.ForeignKey('Network', on_delete=models.CASCADE)
    bts = models.ForeignKey(
        BTS, null=True, blank=True, on_delete=models.SET_NULL)
    imsi = models.CharField(max_length=50, unique=True)
    name = models.TextField()
    crdt_balance = models.TextField(default=crdt.PNCounter("default").serialize())
    state = models.CharField(max_length=10)
    # Time of the last received UsageEvent that's not in NON_ACTIVITIES.
    last_active = models.DateTimeField(null=True, blank=True)
    # Time of the last received UsageEvent that is in OUTBOUND_ACTIVITIES.  We
    # use this attribute to determine when to automatically deactivate a sub.
    last_outbound_activity = models.DateTimeField(null=True, blank=True)
    # This is the time since the MS sent a LUR to the BTS
    last_camped = models.DateTimeField(null=True, blank=True)
    # When toggled, this will protect a subsriber from getting "vacuumed."  You
    # can still delete subs with the usual "deactivate" button.
    prevent_automatic_deactivation = models.BooleanField(default=False)

    @classmethod
    def update_balance(cls, imsi, other_bal):
        """
        Atomically update the balance for a subscriber. Handles reload and
        save.
        """
        with transaction.atomic():
            s = Subscriber.objects.get(imsi=imsi)
            sbal = crdt.PNCounter.from_json(s.crdt_balance)
            new_bal = crdt.PNCounter.merge(other_bal, sbal)
            s.crdt_balance = new_bal.serialize()
            s.save()

    @property
    def balance(self):
        return crdt.PNCounter.from_state(json.loads(self.crdt_balance)).value()

    # this is not really a setter, but adds to the CRDT. As such, it should
    # only work when the CRDT is empty
    # still included to ease creation of subscribers -kurtis
    @balance.setter
    def balance(self, amt):
        try:
            bal = crdt.PNCounter.from_json(self.crdt_balance)
        except ValueError:
            logging.error("Balance string: %s" % (self.crdt_balance, ))
            raise

        if (bal.is_used()):
            raise ValueError("Cannot set the balance of an active CRDT")

        self.change_balance(amt)

    def change_balance(self, amt):
        if (amt == 0):
            return

        try:
            bal = crdt.PNCounter.from_json(self.crdt_balance)
        except ValueError:
            logging.error("Balance string: %s" % (self.crdt_balance, ))
            raise

        if amt > 0:
            bal.increment(amt)
        else:
            bal.decrement(abs(amt))
        self.crdt_balance = bal.serialize()

    def __unicode__(self):
        return "Sub %s, %s, network: %s, balance: %d" % (
            self.name, self.imsi, self.network, self.balance)

    def numbers(self):
        n = self.number_set.all()
        return ", ".join([str(_.number) for _ in n])

    def numbers_as_list(self):
        """Return the sub's associated numbers as a comma-separated list."""
        numbers = self.number_set.all()
        return [str(n.number) for n in numbers]

    def mark_camped(self, last_camped, bts):
        """Updates the last known BTS the subscriber is seen on, as well
           as the time of last activity. Does NOT save.

           Args:
              last_camped: the datetime of last time the MS sent a LUR
              bts: the BTS the subscriber was active on
        """
        # Only register the checkin if the last_camped time is newer
        if not self.last_camped or self.last_camped < last_camped:
            self.last_camped = last_camped
            self.bts = bts

    def deactivate(self):
        """Deactivate a subscriber.

        Send an async post to the BTS to deactivate the subscriber.  Sign the
        request using JWT.  Note that we do not also send deactivate number
        commands -- the BTS will handle that on its own.  If the sub does not
        have an associated BTS, the sub's previous tower may have been deleted.
        We can still delete the sub we just do not have to notify a tower.
        """
        if self.bts:
            url = '%s/config/deactivate_subscriber' % self.bts.inbound_url
            data = {
                'imsi': self.imsi,
                # Add a UUID as a nonce for the message.
                'msgid': str(uuid.uuid4()),
            }
            serializer = itsdangerous.JSONWebSignatureSerializer(
                self.bts.secret)
            signed_data = {
                'jwt': serializer.dumps(data),
            }
            # Retry the async_post for three months until it succeeds.
            retry_delay = 60 * 10
            three_months = 3 * 30 * 24 * 60 * 60.
            max_retries = int(three_months / retry_delay)
            celery_app.send_task(
                'endagaweb.tasks.async_post', (url, signed_data),
                max_retries=max_retries)
        # Deactivate all associated Numbers from this Sub.
        numbers = Number.objects.filter(subscriber=self)
        with transaction.atomic():
            now = django.utils.timezone.now()
            # Create a 'delete_imsi' UsageEvent.
            bts_uuid = None
            if self.bts:
                bts_uuid = self.bts.uuid
            event = UsageEvent.objects.create(
                subscriber=self, date=now, bts=self.bts, kind='delete_imsi',
                subscriber_imsi=self.imsi, bts_uuid=bts_uuid,
                oldamt=self.balance, newamt=self.balance, change=0,
                reason='deactivated subscriber: %s' % self.imsi)
            event.save()
            for number in numbers:
                reason = 'deactivated phone number: %s' % number.number
                event = UsageEvent.objects.create(
                    subscriber=self, date=now, bts=self.bts,
                    kind='deactivate_number', to_number=number.number,
                    reason=reason, oldamt=self.balance, newamt=self.balance,
                    change=0)
                event.save()
                number.network = None
                number.subscriber = None
                number.state = 'available'
                number.save()
            # Actually delete the subscriber.  Note that all associated
            # PendingCreditUpdates will be deleted automatically by the default
            # deletion CASCADE behavior.
            self.delete()

    @property
    def is_camped(self):
        """Determine if the sub is camped.

        Returns:
            True if the Subscriber was active under the T3212 threshold which
            is the time between periodic LURs
        """
        # TODO(omar): this is incomplete status information. We should also
        #             include IMSI detach events. Issue #20 on openbts.
        if self.last_camped is None:
          return False
        t3212_secs = int(ConfigurationKey.objects.get(
            network=self.network, key="GSM.Timer.T3212").value) * 60
        last_camped_secs = (django.utils.timezone.now() - self.last_camped) \
            .total_seconds()
        return last_camped_secs < t3212_secs


class Number(ChargingEntity):
    subscriber = models.ForeignKey(Subscriber, null=True, blank=True,
                                   on_delete=models.SET_NULL)
    network = models.ForeignKey('Network', null=True, blank=True,
                                on_delete=models.CASCADE)
    number = models.CharField(max_length=1024)  # the number (msisdn)
    state = models.CharField(max_length=32)  # 'available', 'pending', 'inuse'
    country_id = models.TextField(null=True)  # country the number belongs to

    def __unicode__(self):
        if self.subscriber and self.network:
            suffix = '%s, %s' % (self.subscriber.imsi, self.network)
        else:
            suffix = '(no IMSI or network)'
        return 'Number %s, state: %s, %s' % (self.number, self.state, suffix)

    def country(self):
        """
        Returns the country ID. We could add some logic here later if this gets
        complicated, but for now since we have one provider we always know the
        country ID of a number, as it's set when we buy the number.
        """
        return self.country_id


class SystemEvent(models.Model):
    """System events, from base stations or cloud.

    These capture informational events or warning/error conditions.
    """
    # For non-BTS-specific events, leave BTS as null. Currently can't see a
    # reason to keep events corresponding to deleted BTSs. This may change.
    bts = models.ForeignKey(BTS, null=True, on_delete=models.CASCADE)
    # Date of event creation
    date = models.DateTimeField()
    # Event types
    type_choices = [
        ('bts up', 'BTS up'),
        ('bts down', 'BTS down')
    ]
    type = models.CharField(max_length=20, choices=type_choices)


class UsageEvent(models.Model):
    """Usage Events sent from various base stations.

    These broadly capture all activity on a network: provisioning subscribers,
    sending and receiving calls and SMS, transferring credit, deleting
    subscribers and adding and removing numbers.

    See the Google Doc on our Django Models for more info, especially regarding
    UsageEvent kinds.

    Attrs:
      transaction_id: a unique identifier for this transaction
      subscriber: a models.Subscriber reference
      subscriber_imsi: the same Subscriber as above, but, if the Subscriber
                       reference is deleted, this field will live on
      bts: a models.BTS reference
      bts_uuid: the same BTS as above, but, if the BTS reference is deleted,
                this field will live on
      network: a Network reference
      date: the date of the event TODO(matt): UTC?
      kind: the type of event (e.g. local_call, transfer, outside_sms, etc) see
            the docs for more info on this field.
      reason: a freeform text field explaining the event
      oldamt: the subscriber's account balance before the event (credits)
      newamt: the subscriber's new account balance after the event (credits)
      change: the cost of this event to the subscriber (credits)
      billsec: the amount of billable seconds in a call
      call_duration: duration of the call in seconds (if this event is a call,
                     otherwise None) -- includes time spent waiting for the
                     call to connect.
      from_imsi: sender IMSI (if applicable)
      from_number: sender number (if applicable and available)
      to_imsi: destination IMSI (if applicable and available)
      to_number: destination number (if applicable and available)
      destination: a Destination instance
      tariff: the cost rate to the subscriber applied for this event in credits
              per unit (if applicable).  E.g. this could be credits per second
              for a call.
              second for a call.
      uploaded_bytes: number of uploaded bytes for a GPRS event
      downloaded_bytes: number of downloaded bytes for a GPRS event
      timespan: the duration of time over which the GPRS data was sampled
    """
    transaction_id = models.UUIDField(editable=False, default=uuid.uuid4)
    subscriber = models.ForeignKey(Subscriber, null=True,
                                   on_delete=models.SET_NULL)
    subscriber_imsi = models.TextField(null=True)
    bts = models.ForeignKey(BTS, null=True, on_delete=models.SET_NULL)
    bts_uuid = models.TextField(null=True)
    network = models.ForeignKey('Network', null=True, on_delete=models.CASCADE)
    date = models.DateTimeField()
    kind = models.TextField()
    reason = models.TextField()
    oldamt = models.BigIntegerField(null=True)
    newamt = models.BigIntegerField(null=True)
    change = models.BigIntegerField(null=True)
    billsec = models.IntegerField(null=True, default=0)
    call_duration = models.IntegerField(null=True, default=0)
    from_imsi = models.CharField(null=True, max_length=64)
    from_number = models.CharField(null=True, max_length=64)
    to_imsi = models.CharField(null=True, max_length=64)
    to_number = models.CharField(null=True, max_length=64)
    destination = models.ForeignKey('Destination', null=True, blank=True,
                                    on_delete=models.CASCADE)
    tariff = models.IntegerField(null=True)
    uploaded_bytes = models.BigIntegerField(null=True)
    downloaded_bytes = models.BigIntegerField(null=True)
    timespan = models.DecimalField(null=True, max_digits=7, decimal_places=1)
    date_synced = models.DateTimeField(auto_now_add=True)

    def voice_sec(self):
        """Gets the number of seconds for this call.

        We previously used call_duration or the event's reason to determine the
        length of the call, but this included time during which the call was
        ringing.  So now we just use billsec.  This corresponds to the value in
        the event's reason anyway.

        Returns:
          floating point duration of a call in seconds
        """
        if self.billsec:
            return self.billsec
        elif "sec call" in self.reason:
            try:
                return int(self.reason.split()[0])
            except:
                pass
        return 0

    def __unicode__(self):
        if self.subscriber:
            return "UsageEvent: %s, %s, %s, %s" % (
                self.subscriber.imsi, self.date, self.kind, self.reason)
        else:
            return "UsageEvent: (deleted IMSI) %s, %s, %s" % (
                self.date, self.kind, self.reason)

    @staticmethod
    def set_imsi_and_uuid_and_network(sender, instance=None, created=False,
                                      **kwargs):
        """Post-create hook to setup UE Sub IMSI, BTS UUID and network data."""
        if not created:
            return
        event = instance
        if event.subscriber and event.subscriber.imsi:
            event.subscriber_imsi = event.subscriber.imsi
        if event.bts and event.bts.uuid:
            event.bts_uuid = event.bts.uuid
        if event.bts and event.bts.network:
            event.network = event.bts.network
        event.save()

    @staticmethod
    def set_subscriber_last_active(sender, instance=None, created=False,
                                   **kwargs):
        """Post-create hook to bump the subscriber's last-active attribute.

        Also bumps the last_outbound_activity attribute if event.kind is in
        OUTBOUND_ACTIVITIES.
        """
        if not created:
            return
        event = instance
        if not event.subscriber:
            # May happen if this was a tower-deregistration event or if the sub
            # was just deleted.
            return

        # make sure event timestamp has timezone info
        if isinstance(event.date, datetime.datetime):
            if django.utils.timezone.is_naive(event.date):
                event.date = django.utils.timezone.make_aware(event.date,
                                                              pytz.utc)
        else:
            logging.warn("expected a datetime value")

        # Some event types do not count towards activity while others count
        # towards outbound activity.
        if event.kind in NON_ACTIVITIES:
            return
        if event.kind in OUTBOUND_ACTIVITIES:
            event.subscriber.last_outbound_activity = event.date
        event.subscriber.last_active = event.date
        event.subscriber.save()


post_save.connect(UsageEvent.set_imsi_and_uuid_and_network, sender=UsageEvent)
post_save.connect(UsageEvent.set_subscriber_last_active, sender=UsageEvent)


class PendingCreditUpdate(models.Model):
    """A credit update that has yet to be acked by a BTS.

    When an operator adds money to a subscriber's account, we will periodically
    send this update to the BTS via a celery repeated task.  When the BTS acks
    the update, we delete this instance.
    """
    date = models.DateTimeField(auto_now_add=True)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE)
    amount = models.BigIntegerField()
    uuid = models.TextField()

    def __unicode__(self):
        return "pending credit update for %s, started %s" % (self.subscriber,
                                                             self.date)

    def req_params(self):
        """Get request params for sending to the BTS."""
        return {
            'imsi': self.subscriber.imsi,
            'change': self.amount,
            'msgid': self.uuid
        }

    def abs_amount(self):
        """Show the absolute value of the credit update's amount."""
        return abs(self.amount)


class Network(models.Model):
    """Every BTS is associated with a network

    Many user profiles can be associated with a particular network (this
    provides some level of multi-user control, but isn't implemented really
    yet). Eventually, things that are associated with just a UserProfile should
    be associated with a Network.

    Networks can calculate the cost to an operator for SMS and calls on their
    network based on the network's associated BillingTiers.
    """

    name = models.TextField(null=True, blank=True, default="Network")
    choices = [
        (currency.code, currency.name) for currency in CURRENCIES.values()]
    subscriber_currency = models.TextField(choices=choices,
                                           default='USD')
    # When buying numbers, we will try to get those that belong to this
    # country.
    number_country = models.CharField(max_length=2, default="US")
    # Bypass authentication to the SIP gateway
    bypass_gateway_auth = models.NullBooleanField(default=0)
    # Whether or not towers on the network should try to auto-upgrade.
    autoupgrade_enabled = models.BooleanField(default=False)
    # The risk/reward preferences of the operator.
    channel_choices = [(v, v) for v in ('stable', 'beta')]
    autoupgrade_channel = models.TextField(
        default='stable', choices=channel_choices)
    # If autoupgrades are enabled, but in_window is False, we will tell the
    # client to autoupgrade as soon as a new release is available.  If this
    # value is True, window_start will be used.
    autoupgrade_in_window = models.BooleanField(default=False)
    # The start of the window in %H:%M:%S format, UTC.
    autoupgrade_window_start = models.TextField(blank=True, null=True,
                                                default='02:30:00')
    # Whether or not to automatically delete inactive subscribers, and
    # associated parameters.
    sub_vacuum_enabled = models.BooleanField(default=False)
    sub_vacuum_inactive_days = models.IntegerField(default=180)

    # csv of endpoints to notify for downtime
    notify_emails = models.TextField(blank=True, default='')
    notify_numbers = models.TextField(blank=True, default='')

    # The user group associated with the network
    auth_group = models.OneToOneField(Group, null=True, blank=True,
                                        on_delete=models.CASCADE)
    # Each network is associated with an auth user that the BTS will use
    # to authenticate on API calls
    auth_user = models.OneToOneField(User, null=True, blank=True,
                                        on_delete=models.CASCADE)
    # Each network is associated with a ledger and its own billing account
    stripe_cust_token = models.CharField(max_length=1024, blank=True,
                                         default="")
    stripe_last4 = models.PositiveIntegerField(blank=True, default=1)
    stripe_card_type = models.TextField(blank=True, default="")
    stripe_exp_mo = models.CharField(max_length=2, blank=True, default="")
    stripe_exp_year = models.CharField(max_length=4, blank=True, default="")
    # Billing.
    autoload_enable = models.BooleanField(default=False)
    recharge_thresh = models.IntegerField(
        default=util_currency.dollars2mc(10),
        blank=True)
    # Based on Stripe fees, we'll get $96.73 per recharge.
    recharge_amount = models.IntegerField(
        default=util_currency.dollars2mc(100),
        blank=True,
        validators=[MinValueValidator(util_currency.dollars2mc(5))],
    )
    # Network billing currency
    currency = models.CharField(max_length=100, default="USD", blank=True,
                                choices=util_currency.supported_currencies())

    # Network environments let you specify things like "prod", "test", "dev",
    # etc so they can be filtered out of alerts. For internal use.
    environment = models.TextField(default="default")

    class Meta:
        permissions = (
            ('view_network', 'View network'),
        )

    @property
    def api_token(self):
        return Token.objects.get(user=self.auth_user)

    @property
    def billing_enabled(self):
        """ Check whether billing is enabled for this network. """
        # currently a global setting, with a test-only override (since
        # we don't have a database field yet to set this)
        return settings.ENDAGA["NW_BILLING"]

    def __unicode__(self):
        return ("Network '%s' connected to %d users" %
                (self.name, len(get_users_with_perms(self, 'view_network'))))

    def pretty_balance(self):
        return humanize_credits(self.ledger.balance)

    def add_credit(self, credit_amount, reason='add credit'):
        """Adds credit to a network.

        Args:
          credit_amount: amount of credit to add (millicents)
          reason: optional reason to include in the transaction

        Returns: True if the operation succeeded so that we can know when to
                 capture authorized charges.
        """
        self.ledger.add_transaction('credit', credit_amount, reason)
        return True

    def bill_for_number(self, number):
        """Bill a network for the cost of a number.

        At the moment, all operators are billed $1/mo for the use of each of
        their Nexmo numbers.

        Args:
          number: the number in use that is causing this charge
        """
        amount = -1 * util_currency.dollars2mc(1)
        kind = 'number.nexmo.monthly'
        reason = 'charge for use of number "%s"' % number
        self.ledger.add_transaction(kind, amount, reason)

    def bill_for_sms(self, cost_to_operator, kind):
        """Creates a transaction billing a network for the cost of an SMS.

        The actual cost is meant to be looked up by another method.

        Args:
          cost_to_operator: the cost per SMS to the operator
          kind: the kind of SMS (see valid Transaction kinds)
        """
        amount = -1 * abs(cost_to_operator)
        reason = 'charge for %s' % kind
        self.ledger.add_transaction(kind, amount, reason)

    def bill_for_call(self, cost_to_operator, billable_seconds, kind):
        """Creates a transaction billing a network for the cost of a call.

        The actual cost is meant to be looked up by another method.

        Args:
          cost_to_operator: the cost per min to the operator
          billable_seconds: the number of seconds to bill for
          kind: the kind of SMS (see valid Transaction kinds)
        """
        if billable_seconds <= 0:
            return
        billable_minutes = billable_seconds / 60.
        amount = int(-1 * abs(cost_to_operator) * billable_minutes)
        reason = 'charge for %s min %s' % (billable_minutes, kind)
        self.ledger.add_transaction(kind, amount, reason)

    def recharge_if_necessary(self):
        """Recharge the account by the recharge_amount if the balance is low.

        TODO(matt): get this working as a post-save handler for Ledgers.

        Returns:
            True if we actually recharged the account, False otherwise
            (including failures).
        """
        if not self.billing_enabled:
            # avoid attempt to charge card for recharge
            return False

        if self.recharge_amount <= 0:
            return False
        if self.ledger.balance >= self.recharge_thresh:
            return False
        try:
            charge = self.authorize_card(self.recharge_amount)
            result = self.add_credit(self.recharge_amount,
                                     'Automatic Recharge')
            if result:
                self.capture_charge(charge.id)
                return True
            else:
                return False
        except stripe.StripeError:
            # TODO(matt): alert the staff.
            logger.error('Recharge failed for %s' % (self, ))
            return False

    def update_card(self, token):
        """Adds a new card for this network.

        First, delete whatever we have on file, then add the new stuff.

        Returns:
            True if card was successfully added, False otherwise.
        """
        if self.delete_card():
            try:
                # This will raise a stripe.CardError if it doesn't succeed.
                text = "%s (id %d)" % (self.name, self.id)
                customer = stripe.Customer.create(card=token, description=text)
            except stripe.CardError:
                return False

            self.stripe_last4 = customer["cards"]["data"][0]["last4"]
            self.stripe_card_type = customer["cards"]["data"][0]["brand"]
            self.stripe_cust_token = customer["id"]
            self.stripe_exp_mo = customer["cards"]["data"][0]["exp_month"]
            self.stripe_exp_year = customer["cards"]["data"][0]["exp_year"]
            self.save()
            return True
        else:
            raise ValueError("Couldn't delete the existing card!")

    def authorize_card(self, amount_in_mc):
        """This authorizes an amount on a card. Note this does *not* actually
        charge the card; you must capture the charge later to complete the
        transaction. Usage is as follows:

            charge = self.authorize_card(amount)
            complex_function_that_might_fail()
            self.capture_charge(charge.id)

        Doing this in two steps ensures that we don't accidentally double
        charge the card if the complex function fails in some unexpected way.

        For example, say we were updating the account balance; if our DB failed
        and we couldn't actually update the network's balance, we don't want to
        actually charge their credit card. Authorizations automatically expire
        if they aren't captured, which prevents overcharge.

        Returns:
            a Charge created by stripe
        """
        pennies = util_currency.mc2cents(amount_in_mc)
        customer = stripe.Customer.retrieve(self.stripe_cust_token)
        charged = stripe.Charge.create(amount=pennies, currency="usd",
                                       customer=customer.id, capture=False)
        return charged

    def capture_charge(self, charge_id):
        """
        Captures an existing charge. See authorize_card for more info on usage.

        Returns the charge object (captured parameter should be set to "true")
        if successful or raises an error otherwise.
        """
        charge = stripe.Charge.retrieve(charge_id)
        charge.capture()
        return charge

    def delete_card(self):
        """Delete the customer's card from our DB, and clear with stripe.

        Returns:
          True if the retrieve call fails or if we successfully delete the
          customer, and if we successfully remove the card info from the db.
          False otherwise.
        """
        # Apparently the recommended way to do this is to delete the customer
        # object?
        try:
            customer = stripe.Customer.retrieve(self.stripe_cust_token)
            customer.delete()
            # TODO(matt): simplify this if-logic or use
            #             `return 'deleted' in dict(customer)` (see #104)
            if not "deleted" in dict(customer):
                return False
        except stripe.InvalidRequestError:
            pass

        self.stripe_cust_token = ""
        self.stripe_card_type = ""
        self.stripe_last4 = 1
        self.stripe_exp_mo = ""
        self.stripe_exp_year = ""
        self.save()
        return True


    def calculate_operator_cost(self, directionality, sms_or_call,
                                destination_number=''):
        """Calculates the cost to an operator of a call or SMS.

        For local and inbound traffic, lookup the billing tier attached to this
        network and return the cost of an SMS or call.  We're still operating
        in a simple world where there is only one off-network receive tier and
        only two on-network billing tiers (send and receive).

        For off-network sent traffic, look at all Destinations and find the
        best match for the destination number.  Figure out this Destination's
        Destination Group and then find the associated Billing Tier.

        Args:
          directionality: one of off_network_send, off_network_receive,
                          on_network_send or on_network_receive
          sms_or_call: on of sms or call
          destination_number: the number that was called or texted

        Returns:
          the cost to the operator per SMS or the cost per minute of voice call
          in millicents
        """
        if directionality in ('off_network_receive', 'on_network_send',
                              'on_network_receive'):
            tier = BillingTier.objects.get(
                network=self, directionality=directionality)
        elif (directionality == 'off_network_send' and
              self.get_lowest_tower_version() is None):
            # If the network's lowest tower version is too low to support
            # Billing Tiers, we should bill all off_network_send events on
            # Tier A, as that's the only Tier that will be shown to the
            # operator.
            tier = BillingTier.objects.get(
                network=self, name='Off-Network Sending, Tier A',
                directionality='off_network_send')
        elif directionality == 'off_network_send':
            # The longest prefix in the Nexmo spreadsheet is four digits long,
            # so we'll take the first four digits of the destination_number and
            # try to match that against a prefix.  If it fails, we'll pop off
            # a digit and try again to find a match, etc.
            # TODO(shaddi): A trie would be more flexible here/would only
            # require one DB lookup (or even keep that cached in memory),
            # perhaps we should use that instead.
            # First strip any '+' signs out of the number.
            destination_number = destination_number.strip('+')
            possible_prefix = destination_number[0:5]
            while possible_prefix:
                try:
                    destination = Destination.objects.get(
                        prefix=possible_prefix)
                    break
                except Destination.DoesNotExist:
                    # Pop the last digit.
                    possible_prefix = possible_prefix[0:-1]
            if len(possible_prefix) == 0:
                raise ValueError("No billing dest for %s" % destination_number)
            # Find the BillingTier associated with this Destination's
            # DestinationGroup.
            tier = BillingTier.objects.get(
                network=self, destination_group=destination.destination_group,
                directionality=directionality)
        if sms_or_call == 'sms':
            return tier.cost_to_operator_per_sms
        elif sms_or_call == 'call':
            return tier.cost_to_operator_per_min

    def guru_settings(self):
        """Returns a list of advanced configuration settings.

        These, in general, should not be exposed to or touched by the end user.
        """
        advanced = ['GSM.Identity.MCC', 'GSM.Identity.MNC',
                    'Control.LUR.OpenRegistration', 'GSM.Timer.T3212']
        return ConfigurationKey.objects.filter(
            key__in=advanced, network=self).order_by('key')

    def _set_configuration_default(self):
        """A post-create hook for Networks to create default ConfigKeys."""
        defaults = {}
        defaults['openbts'] = {
            'GSM.Identity.MCC': '901',
            'GSM.Identity.MNC': '55',
            'GSM.Identity.ShortName': self.name,
            'Control.LUR.OpenRegistration': "^90155",
            'GSM.Timer.T3212': 12  # minutes
        }
        for cat in defaults:
            for k in defaults[cat]:
                c = ConfigurationKey(network=self, category=cat, key=k,
                                     value=defaults[cat][k])
                c.save()
        self.set_open_registration()

    def set_open_registration(self):
        mcc = ConfigurationKey.objects.get(
            network=self, key="GSM.Identity.MCC").value
        mnc = ConfigurationKey.objects.get(
            network=self, key="GSM.Identity.MNC").value
        openreg = "^%s%s" % (mcc, mnc)
        c, created = ConfigurationKey.objects.get_or_create(
            network=self, key="Control.LUR.OpenRegistration")
        if created:
            # Don't overwrite the existing value.
            c.value = openreg
            c.save()

    def get_lowest_tower_version(self):
        """Get the lowest metapackage version for all towers on the Network.

        We'll use this to determine the capabilities of the network, and to
        control what we show to the operator in the dashboard UI.
        """
        towers = BTS.objects.filter(network=self)
        versions = []
        for tower in towers:
            if tower.status == 'no-data':
                continue
            try:
                package_versions = json.loads(tower.package_versions)
                versions.append(package_versions['endaga_version'])
            except AttributeError:
                versions.append(None)
        if not versions:
            return None
        return min(versions)

    def get_outbound_inactive_subscribers(self, days):
        """Finds subscribers without outbound activity for some days.

        Args:
          days: the cutoff time that defines outbound inactivity

        Returns: a list of Subscriber instances
        """
        # First find all subscribers that haven't had outbound activity for a
        # while.
        threshold = (django.utils.timezone.now() -
                     datetime.timedelta(days=days))
        outbound_inactive_subs = list(Subscriber.objects.filter(
            network=self, last_outbound_activity__lt=threshold))
        # Also find subscribers that have never had outbound activity.  Return
        # these subs too if they were registered before the threshold.
        never_outbound_active_subs = Subscriber.objects.filter(
            network=self, last_outbound_activity=None)
        for sub in never_outbound_active_subs.iterator():
            try:
                last_event = UsageEvent.objects.filter(
                    subscriber=sub).order_by('-date')[0]
                if last_event.date < threshold:
                    outbound_inactive_subs.append(sub)
            except IndexError:
                # These subs never had any UEs at all, strangely.
                outbound_inactive_subs.append(sub)
        return outbound_inactive_subs

    @staticmethod
    def ledger_save_handler(sender, instance, created, **kwargs):
        """When a ledger is saved, see if we need to recharge the account and
        recharge the account by the recharge_amount if the balance is low.

        Do nothing if the ledger was just created or if the network does not
        have autoload enabled.

        Args:
          instance: a Ledger instance
        """
        network = Network.objects.get(ledger=instance)
        if created or not (network.billing_enabled and
                           network.autoload_enable):
            return
        network.recharge_if_necessary()

    @staticmethod
    def set_network_defaults(sender, instance=None, created=False, **kwargs):
        """Post-create hook to setup network default settings."""
        if created:
            network = instance
            network._set_configuration_default()

    @staticmethod
    def create_billing_tiers(sender, instance, created, **kwargs):
        """Post-create hook: on creating a Network, setup billing tiers.

        Will also create DestinationGroups and Destinations if these do not yet
        exist.

        Args:
          sender: the model sending this post-save hook
          instance: the instance that was saved
          created: boolean, indicates whether the instance was just created
        """
        if not created:
            return
        tier_data = tier_setup.create_tier_data()
        off_send_tiers = [t for t in tier_data
                          if t['directionality'] == 'off_network_send']
        # Create Destinations and DestinationGroups if they do not yet exist.
        destination_groups = DestinationGroup.objects.all()
        destinations = Destination.objects.all()
        if not destination_groups or not destinations:
            for tier in off_send_tiers:
                new_destination_group = DestinationGroup(name=tier['name'])
                new_destination_group.save()
                for destination in tier['destinations']:
                    new_destination = Destination(
                        country_code=destination['country_code'],
                        country_name=destination['country_name'],
                        destination_group=new_destination_group,
                        prefix=destination['prefix']
                    )
                    new_destination.save()
        # Create the billing tiers themselves, off_network_send first.
        for tier in off_send_tiers:
            destination_group = DestinationGroup.objects.filter(
                name=tier['name'])[0]
            new_billing_tier = BillingTier(
                cost_to_operator_per_min=tier['cost_to_operator_per_min'],
                cost_to_operator_per_sms=tier['cost_to_operator_per_sms'],
                cost_to_subscriber_per_min=tier['cost_to_subscriber_per_min'],
                cost_to_subscriber_per_sms=tier['cost_to_subscriber_per_sms'],
                destination_group=destination_group,
                directionality='off_network_send',
                name=tier['name'],
                network=instance
            )
            new_billing_tier.save()
        # Create off_network_send and on/off_network_receive tiers.
        for tier in tier_data:
            if tier['directionality'] == 'off_network_send':
                continue
            new_billing_tier = BillingTier(
                cost_to_operator_per_min=tier['cost_to_operator_per_min'],
                cost_to_operator_per_sms=tier['cost_to_operator_per_sms'],
                cost_to_subscriber_per_min=tier['cost_to_subscriber_per_min'],
                cost_to_subscriber_per_sms=tier['cost_to_subscriber_per_sms'],
                directionality=tier['directionality'],
                name=tier['name'],
                network=instance
            )
            new_billing_tier.save()

    @staticmethod
    def create_auth(sender, instance, created, **kwargs):
        """
        A hook that run when we create a new network that creates
        an auth user and token that BTSs on the network use to
        authenticate.
        """
        if not instance.auth_group or not instance.auth_user:
            instance.auth_group, created_group = Group.objects.get_or_create(name='network_%s'
                % instance.pk)
            if created_group:
                assign_perm('view_network', instance.auth_group, instance)

            post_save.disconnect(UserProfile.new_user_hook, sender=User)
            instance.auth_user, created_user = User.objects.get_or_create(username='network_%s'
                % instance.pk)
            if created_user:
                Token.objects.create(user=instance.auth_user)
                instance.auth_group.user_set.add(instance.auth_user)
            post_save.connect(UserProfile.new_user_hook, sender=User)
            instance.save()

    @staticmethod
    def create_ledger(sender, instance, created, **kwargs):
        if not Ledger.objects.filter(network=instance).exists():
            Ledger.objects.create(network=instance)

# Whenever we update the Ledger, attempt to recharge the Network bill.
post_save.connect(Network.ledger_save_handler, sender=Ledger)

post_save.connect(Network.create_ledger, sender=Network)
post_save.connect(Network.create_auth, sender=Network)
post_save.connect(Network.set_network_defaults, sender=Network)
post_save.connect(Network.create_billing_tiers, sender=Network)


class NetworkDenomination(models.Model):
    """Network has its own denomination bracket for rechange and validity

    Subscriber status depends on recharge under denomination bracket
    """
    start_amount = models.BigIntegerField()
    end_amount = models.BigIntegerField()
    validity_days = models.PositiveIntegerField(blank=True, default=0)

    # The denomination group associated with the network
    network = models.ForeignKey('Network', null=True, on_delete=models.CASCADE)

    def __unicode__(self):
        return "Amount %s - %s  for %s day(s)" % (
            humanize_credits(self.start_amount,
                             CURRENCIES[self.network.subscriber_currency]),
            humanize_credits(self.end_amount,
                             CURRENCIES[self.network.subscriber_currency]),
            self.validity_days)

    class Meta:
        ordering = ('start_amount',)


class ConfigurationKey(models.Model):
    """A key->value mapping for storing settings.

    Can be associated with many things.
    """
    bts = models.ForeignKey(BTS, null=True, blank=True, on_delete=models.CASCADE)
    network = models.ForeignKey(Network, null=True, blank=True,
                                on_delete=models.CASCADE)
    category = models.TextField()  # "endaga", "openbts", etc..
    key = models.TextField()
    value = models.TextField()

    def __unicode__(self):
        related_str = ""
        if self.network:
            related_str += "Network %s" % self.network.name
            if self.bts:
                related_str += " BTS %s" % self.bts.uuid
        return "ConfKey: %s, category %s | %s -> %s" % (
            related_str, self.category, self.key, self.value)


class BillingTier(models.Model):
    """A network billing tier.

    This is how we charge operators and allow operators to set prices for their
    subscribers.  All costs to operators are in millicents; all costs to
    subscribers are in currency-agnostic "credits".  Credits are always integer
    values that, when combined with a currency code, can yield a useful value.

    Each network will have seven associated billing tiers: four
    off_network_send tiers, and one each of an off_network_receive,
    on_network_send and on_network_receive tier.  These four 'classes' of tiers
    are captured in the 'directionality' attribute of the BillingTier.

    Tiers map directly to DestinationGroups and operators can completely
    disable connectivity to a DG via the traffic_enabled flag.
    """
    cost_to_operator_per_min = models.IntegerField(default=0)
    cost_to_operator_per_sms = models.IntegerField(default=0)
    cost_to_subscriber_per_min = models.IntegerField(default=0)
    cost_to_subscriber_per_sms = models.IntegerField(default=0)
    # on_network_send, on_network_receive and off_network_receive BillingTiers
    # will not have an associated DestinationGroup.  We set blank to True so
    # that we can edit non off_network_send BTs in django-admin.
    destination_group = models.ForeignKey('DestinationGroup', null=True,
                                          blank=True, on_delete=models.CASCADE)
    choices = [(v, v) for v in ('on_network_receive', 'on_network_send',
                                'off_network_receive', 'off_network_send')]
    directionality = models.TextField(choices=choices)
    name = models.TextField(default='Billing Tier')
    network = models.ForeignKey('Network', null=True, on_delete=models.CASCADE)
    traffic_enabled = models.BooleanField(default=True)
    billable_unit = models.IntegerField(default=1)  # Increment to bill (secs)

    def __unicode__(self):
        return ('BillingTier "%s" connected to Network "%s"' % (self.name,
                                                                self.network))


class DestinationGroup(models.Model):
    """A set of Destinations.

    There will be a small number of DGs shared amongst all networks.  Endaga
    uses these to adjust prices for all networks globally.  Each billing tier
    is associated to one DG.
    """
    name = models.TextField()

    def __unicode__(self):
        return 'DestinationGroup %s' % self.name


class Destination(models.Model):
    """A provider prefix from their billing list.

    The prefix attribute is likely the country's phone code but could be
    longer.
    """
    country_code = models.TextField()
    country_name = models.TextField()
    destination_group = models.ForeignKey('DestinationGroup', null=True,
                                            on_delete=models.CASCADE)
    prefix = models.TextField()

    def __unicode__(self):
        return 'Destination for %s, prefix: %s, group: %s' % (
            self.country_name, self.prefix, self.destination_group)


class DeregisteredBTS(models.Model):
    """Towers that have been deregistered.

    An instance of this model is created when a tower is deregistered and the
    BTS model is deleted.  Then, if a tower with the same UUID checks in, a
    special checkin response is generated.  This response informs the client
    that it should factory-reset itself and restart its services.

    We copy the original tower's secret so that we can properly sign the
    checkin response.
    """
    uuid = models.CharField(max_length=255, unique=True)
    secret = models.TextField(null=True)


class ClientRelease(models.Model):
    """Tracks client software releases on various channels.

    When new client software is released to a channel, we should create a new
    instance of this model via staff.endaga.
    """
    # When this client release was created.
    date = models.DateTimeField()
    # A human-readable string representing the metapackage version
    # (e.g. 0.3.12).
    version = models.TextField()
    # The channel on which this release is available.  Note that if there is
    # one package available on two channels, there will just be two instances
    # of this model.
    channel_choices = [(v, v) for v in ('stable', 'beta')]
    channel = models.TextField(choices=channel_choices)


class Lock(models.Model):
    """
    A DB-backed lock. It emulates a compare-and-swap though is slightly
    different from the traditional CAS operation. It also implements a timeout
    so locks can expire automatically.

    Locks have names that are globally unique. Clients take a lock by calling
    the grab() static method and can release the lock using the release()
    static method. This is the recommended API as it handles transaction
    control and reloading for the caller.

    Examples

    Creating a lock:
        # Creates then sets 'my_uuid' to the lock 'lock_name'
        Lock.grab('lock_name', 'my_uuid')

    Grabbing a lock:

        # Creates then sets 'my_uuid' to the lock 'lock_name'
        Lock.grab('lock_name', 'my_uuid')

        Lock.grab('lock_name', 'my_uuid') # returns True
        Lock.grab('lock_name', 'other_uuid') # returns False

    Creating/grabbing a lock with a timeout:

        Lock.grab('name', 'my_uuid', ttl=30)
        Lock.grab('name', 'other_uuid') # returns False
        time.sleep(30)
        Lock.grab('name', 'other_uuid') # returns True
    """
    key = models.TextField(unique=True)
    value = models.TextField(null=True)
    ttl = models.IntegerField(null=True)
    updated = models.DateTimeField(auto_now=True)

    def is_expired(self):
        # get postgres timestamp to determine if it's expired
        if not self.ttl:
            return False
        now = dbutils.get_db_time(connection)
        return (now - self.updated).total_seconds() > self.ttl

    def lock(self, value):
        """
        NOTE: You probably don't want to use this method directly, see grab().

        If the value is None or the same as the value the lock-seeker is trying
        to set, the lock() method will return True and update the lock's value,
        and False otherwise.
        """
        if self.value is None or self.value == value or self.is_expired():
            self.value = value
            self.save()
            return True
        return False

    def unlock(self, value):
        """
        NOTE: You probably don't want to use this method directly, see
        release().

        If the value matches the value set by the lock-releaser, release the
        lock and return True. False otherwise.
        """
        if self.value == value:
            self.value = None
            self.save()
            return True
        return False

    @staticmethod
    def grab(lock_name, lock_value, ttl=None):
        """
        Creates and grabs locks. Always runs inside an atomic transaction and
        reloads lock object before every operation.

        Args:
            lock_name:  The name of the lock to use. If a lock of this name
                        does not exist, we create the lock and immediately take
                        hold of it.
            lock_value: The value to set to the lock.
            ttl:        The timeout of the lock. Only has effect the first time
                        a lock is created (once a lock has a TTL, it can't be
                        changed).

        Returns:
            True if the lock is held by the caller, false otherwise.
        """
        with transaction.atomic():
            try:
                l = Lock.objects.get(key=lock_name)
            except Lock.DoesNotExist:
                l = Lock(key=lock_name, ttl=ttl)
            return l.lock(lock_value)

    @staticmethod
    def wait(lock_name, lock_value, ttl=None, wait_time=1):
        """
        Blocking version of grab(). wait_time defines how long we wait before
        retrying to take the lock.
        """
        while True:
            if Lock.grab(lock_name, lock_value, ttl=ttl):
                return True
            time.sleep(wait_time)

    @staticmethod
    def release(lock_name, lock_value):
        """
        Release the lock of lock_name if its value matches lock_value. Returns
        true if we released the lock, or false otherwise.

        Note that this will fail if the lock is not held by anyone (i.e., the
        lock value is None).
        """
        with transaction.atomic():
            l = Lock.objects.get(key=lock_name)
            return l.unlock(lock_value)


class TimeseriesStat(models.Model):
    """Flexible timeseries statistics.

    These are typically BTS-reported values like channel load.  As such, we
    will keep the default on-delete 'cascade' behavior and delete these
    instances when the linked BTS is deleted.
    """
    key = models.TextField()
    value = models.DecimalField(null=True, max_digits=12, decimal_places=3)
    date = models.DateTimeField()
    bts = models.ForeignKey(BTS, null=True, blank=True, on_delete=models.CASCADE)
    network = models.ForeignKey('Network', on_delete=models.CASCADE)

class BTSLogfile(models.Model):
    """This model stores log file uploads that have come from client.
    Until we get S3 or something similar setup, we are storing file data
    in postgres.
    """

    uuid = models.UUIDField(editable=False, default=uuid.uuid4)
    requested = models.DateTimeField(auto_now_add=True)
    logfile = models.FileField(upload_to='logfiles/', null=True, blank=True)
    log_name = models.CharField(max_length=60,
        choices=[('syslog', 'Syslog'), ('endaga', 'Endaga')])
    task_id = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=10, default='pending',
        choices=[('pending', 'Pending'), ('trying', 'Trying'),
            ('error', 'Error'), ('accepted', 'Accepted'), ('done', 'Done')])
    window_start = models.DateTimeField(blank=True, null=True,
        help_text='Gather log entries after this time')
    window_end = models.DateTimeField(blank=True, null=True,
        help_text='Gather log entries before this time')
    bts = models.ForeignKey(BTS, on_delete=models.CASCADE)

    def req_params(self):
        return {
          'start': self.window_start.isoformat('T') if self.window_start else 'None',
          'end': self.window_end.isoformat('T') if self.window_end else 'None',
          'log_name': self.log_name,
          'msgid': str(self.uuid)
        }

    def save(self, *args, **kwargs):
        # this is a new object
        if not self.pk:
            super(BTSLogfile, self).save(*args, **kwargs)
            task = celery_app.send_task('endagaweb.tasks.req_bts_log',
                (self,))
            self.task_id = task.id
        super(BTSLogfile, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super(BTSLogfile, self).delete(*args, **kwargs)
        celery_app.control.revoke(self.task_id)
        if self.logfile:
            self.logfile.delete()

class FileUpload(models.Model):
    name = models.CharField(max_length=255, primary_key=True)
    data = models.BinaryField(default='')  # a base64 encoded TextField
    size = models.BigIntegerField(default=0)
    created_time = models.DateTimeField(auto_now_add=True)
    modified_time = models.DateTimeField(auto_now_add=True)
    accessed_time = models.DateTimeField(auto_now=True)
