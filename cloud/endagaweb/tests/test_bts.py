"""Tests for models.BTS.

Usage:
    $ python manage.py test endagaweb.BTSHandleEventTestCase
    $ python manage.py test endagaweb.BTSCheckinResponseTest
    $ python manage.py test endagaweb.ChargeOperatorOnEventCreationTest

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import time

from datetime import datetime, timedelta
import json
from unittest import TestCase

from django.test import TestCase as DjangoTestCase
from django.conf import settings
import django.utils.timezone
import itsdangerous
import mock
import pytz
from rest_framework.test import APIClient

from endagaweb import checkin
from endagaweb import models
from endagaweb import notifications
from endagaweb import tasks

import syslog
from endagaweb.ic_providers.nexmo import NexmoProvider


class BTSHandleEventTestCase(TestCase):
    """Testing the BTS model's ability to handle incoming usage events."""

    @classmethod
    def setUpClass(cls):
        """Using setUpClass so we don't create duplicate objects."""
        cls.user = models.User(username="zzz", email="z@e.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        # mock out notifications' celery
        cls.old_celery_app = notifications.celery_app
        notifications.celery_app = mock.MagicMock()

        cls.bts = models.BTS(uuid="224466", nickname="test-bts-name",
                             inbound_url="http://localhost/224466/test",
                             network=cls.user_profile.network)
        cls.bts.save()
        cls.subscriber_imsi = 'IMSI000456'
        cls.subscriber = models.Subscriber.objects.create(
            balance=10000, name='test-sub-name', imsi=cls.subscriber_imsi,
            network=cls.bts.network)
        cls.subscriber.save()

    @classmethod
    def tearDownClass(cls):
        """Delete some of the things we created."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.subscriber.delete()

        notifications.celery_app = cls.old_celery_app

    def setUp(self):
        # Delete all pre-existing events.
        for usage_event in models.UsageEvent.objects.all():
            usage_event.delete()
        # For event generation, see core.events._create_event in the client
        # repo.
        self.incoming_event = {
            'date': '2015-02-15 15:32:43',
            'imsi': self.subscriber_imsi,
            'oldamt': 1000,
            'newamt': 900,
            'change': 100,
            'reason': 'test reason',
            'kind': 'outside_call',
            'billsec': 45,
            'call_duration': 55,
            'from_imsi': 'IMSI000123',
            'from_number': '5550123',
            'to_imsi': 'IMSI000987',
            'to_number': '6285550987',
            'tariff': 350,
            'seq': 3,
        }
        checkin.handle_event(self.bts, self.incoming_event)
        self.new_usage_event = models.UsageEvent.objects.all()[0]

    def tearDown(self):
        # Reset the max sequence number.
        self.bts.max_seqno = 0

    def test_date(self):
        event_date = self.new_usage_event.date.strftime('%Y-%m-%d %H:%M:%S')
        self.assertEqual(self.incoming_event['date'], event_date)

    def test_imsi(self):
        """A reference to the sub and the sub's IMSI should both be saved."""
        self.assertEqual(self.subscriber_imsi,
                         self.new_usage_event.subscriber.imsi)
        self.assertEqual(self.subscriber_imsi,
                         self.new_usage_event.subscriber_imsi)

    def test_bts(self):
        """A reference to the BTS and the BTS's UUID should both be saved."""
        self.assertEqual(self.bts, self.new_usage_event.bts)
        self.assertEqual(self.bts.uuid, self.new_usage_event.bts_uuid)

    def test_network(self):
        """A reference to the network should be saved."""
        self.assertEqual(self.bts.network, self.new_usage_event.network)

    def test_oldamt(self):
        self.assertEqual(self.incoming_event['oldamt'],
                         self.new_usage_event.oldamt)

    def test_newamt(self):
        self.assertEqual(self.incoming_event['newamt'],
                         self.new_usage_event.newamt)

    def test_change(self):
        self.assertEqual(self.incoming_event['change'],
                         self.new_usage_event.change)

    def test_reason(self):
        self.assertEqual(self.incoming_event['reason'],
                         self.new_usage_event.reason)

    def test_kind(self):
        self.assertEqual(self.incoming_event['kind'],
                         self.new_usage_event.kind)

    def test_billsec(self):
        self.assertEqual(self.incoming_event['billsec'],
                         self.new_usage_event.billsec)

    def test_call_duration(self):
        self.assertEqual(self.incoming_event['call_duration'],
                         self.new_usage_event.call_duration)

    def test_from_imsi(self):
        self.assertEqual(self.incoming_event['from_imsi'],
                         self.new_usage_event.from_imsi)

    def test_from_number(self):
        self.assertEqual(self.incoming_event['from_number'],
                         self.new_usage_event.from_number)

    def test_to_imsi(self):
        self.assertEqual(self.incoming_event['to_imsi'],
                         self.new_usage_event.to_imsi)

    def test_to_number(self):
        self.assertEqual(self.incoming_event['to_number'],
                         self.new_usage_event.to_number)

    def test_tariff(self):
        self.assertEqual(self.incoming_event['tariff'],
                         self.new_usage_event.tariff)

    def test_voice_sec_with_call_duration(self):
        self.assertEqual(self.incoming_event['billsec'],
                         self.new_usage_event.voice_sec())

    def test_voice_sec_sans_call_duration(self):
        """We can still parse voice seconds without the call duration key."""
        incoming_event = {
            'date': '2015-02-15 15:32:43',
            'imsi': self.subscriber_imsi,
            'oldamt': 800,
            'newamt': 700,
            'change': 100,
            'reason': '30 sec call',
            'kind': 'local_call',
            'billsec': 30,
            'seq': 100,
        }
        checkin.handle_event(self.bts, incoming_event)
        new_usage_event = models.UsageEvent.objects.filter(
            kind__exact='local_call')[:1].get()
        self.assertEqual(30, new_usage_event.voice_sec())

    def test_call_with_no_billsec(self):
        """Events can be generated with no 'billsec' key."""
        incoming_event = {
            'date': '2015-02-15 15:32:43',
            'imsi': self.subscriber_imsi,
            'oldamt': 800,
            'newamt': 700,
            'change': 100,
            'reason': '70 sec call',
            'kind': 'local_call',
            'seq': 101,
        }
        checkin.handle_event(self.bts, incoming_event)
        new_usage_event = models.UsageEvent.objects.filter(
            kind__exact='local_call')[:1].get()
        self.assertEqual(70, new_usage_event.voice_sec())

    def test_destination(self):
        """The destination should be set as this event has a to_number."""
        expected = models.Destination.objects.get(country_code='ID')
        self.assertEqual(expected, self.new_usage_event.destination)


class CheckinResponseTest(TestCase):
    """Testing the BTS model's ability to generate a checkin response.

    See example data structures in endagaweb.models.BTS._gather_configuration.
    """

    @classmethod
    def setUpClass(cls):
        """Using setUpClass so we don't create duplicate objects."""
        cls.user = models.User(username="kaz", email="l@f.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        # mock out notifications' celery
        cls.old_celery_app = notifications.celery_app
        notifications.celery_app = mock.MagicMock()

        cls.bts = models.BTS(uuid="234123", nickname="test-bts-name",
                             inbound_url="http://localhost/334455/test",
                             network=cls.user_profile.network)
        cls.bts.save()
        cls.bts2 = models.BTS(uuid="b234123b", nickname="test-bts2-name",
                             inbound_url="http://localhost/33445566/test",
                             network=cls.user_profile.network)
        cls.bts2.save()
        # Set some network autoupgrade preferences.
        cls.user_profile.network.autoupgrade_enabled = True
        cls.user_profile.network.autoupgrade_channel = 'beta'
        cls.user_profile.network.autoupgrade_in_window = True
        cls.user_profile.network.autoupgrade_window_start = '12:34:56'
        cls.user_profile.network.save()
        # Create two client releases.
        feb3 = datetime(year=2020, month=2, day=3, hour=21, tzinfo=pytz.utc)
        cls.stable_release = models.ClientRelease(date=feb3, version='1.2.34',
                                                  channel='stable')
        cls.stable_release.save()
        aug10 = datetime(year=2020, month=8, day=10, hour=13, tzinfo=pytz.utc)
        cls.beta_release = models.ClientRelease(date=aug10, version='5.6.78',
                                                channel='beta')
        cls.beta_release.save()
        # Generate a checkin response which will be evaluated in the tests.
        status = {}
        cls.checkin_response = checkin.CheckinResponder(cls.bts).process(status)
        cls.prices = cls.checkin_response['config']['prices']

    @classmethod
    def tearDownClass(cls):
        """Delete some of the things we created."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.user_profile.network.delete()
        cls.stable_release.delete()
        cls.beta_release.delete()

        notifications.celery_app = cls.old_celery_app

    def test_response_is_dict(self):
        self.assertTrue(isinstance(self.checkin_response, dict))

    def test_config_prices_is_list(self):
        self.assertTrue(isinstance(self.prices, list))

    def test_price_is_dict(self):
        first_price = self.prices[0]
        self.assertTrue(isinstance(first_price, dict))

    def test_price_has_country_data(self):
        off_send_prices = [p for p in self.prices
                           if p['directionality'] == 'off_network_send']
        price = off_send_prices[0]
        self.assertTrue('prefix' in price)
        self.assertTrue('country_name' in price)
        self.assertTrue('country_code' in price)

    def test_price_has_cost_data(self):
        price = self.prices[0]
        self.assertTrue('cost_to_subscriber_per_min' in price)
        self.assertTrue('cost_to_subscriber_per_sms' in price)

    def test_number_of_off_network_receive_tiers(self):
        off_receive_prices = [p for p in self.prices
                              if p['directionality'] == 'off_network_receive']
        self.assertEqual(1, len(off_receive_prices))

    def test_number_of_on_network_receive_tiers(self):
        on_receive_prices = [p for p in self.prices
                             if p['directionality'] == 'on_network_receive']
        self.assertEqual(1, len(on_receive_prices))

    def test_number_of_on_network_send_tiers(self):
        on_send_prices = [p for p in self.prices
                          if p['directionality'] == 'on_network_send']
        self.assertEqual(1, len(on_send_prices))

    def test_default_number_country(self):
        expected_country = 'US'
        self.assertEqual(
            expected_country,
            self.checkin_response['config']['endaga']['number_country'])

    def test_adjusted_number_country(self):
        """We can change the number country and send it to the BTS."""
        new_number_country = 'CL'
        self.user_profile.network.number_country = new_number_country
        self.user_profile.network.save()
        status = {}
        checkin_response = checkin.CheckinResponder(self.bts).process(status)
        self.assertEqual(
            new_number_country,
            checkin_response['config']['endaga']['number_country'])

    def test_default_currency_code(self):
        expected_currency_code = 'USD'
        self.assertEqual(
            expected_currency_code,
            self.checkin_response['config']['endaga']['currency_code'])

    def test_adjusted_currency_code(self):
        new_currency_code = 'IDR'
        self.user_profile.network.subscriber_currency= new_currency_code
        self.user_profile.network.save()
        status = {}
        checkin_response = checkin.CheckinResponder(self.bts).process(status)
        self.assertEqual(
            new_currency_code,
            checkin_response['config']['endaga']['currency_code'])

    def test_autoupgrade_preferences(self):
        """We send autoupgrade preferences to the tower."""
        autoupgrade_values = self.checkin_response['config']['autoupgrade']
        self.assertEqual(True, autoupgrade_values['enabled'])
        self.assertEqual('beta', autoupgrade_values['channel'])
        self.assertEqual(True, autoupgrade_values['in_window'])
        self.assertEqual('12:34:56', autoupgrade_values['window_start'])
        self.assertEqual('1.2.34', autoupgrade_values['latest_stable_version'])
        self.assertEqual('5.6.78', autoupgrade_values['latest_beta_version'])

    def test_bts_config_precedence(self):
        openbts_conf = self.checkin_response['config']['openbts']
        self.assertEqual('901', str(openbts_conf['GSM.Identity.MCC']))

        # Add a BTS-specific ConfigurationKey to change the value
        ck = models.ConfigurationKey.objects.get(network=self.user_profile.network, key='GSM.Identity.MCC')
        ck.pk = None # clone new object
        ck.bts = self.bts
        ck.value = "123"
        ck.save()

        status = {}
        checkin_response = checkin.CheckinResponder(self.bts).process(status)
        openbts_conf = checkin_response['config']['openbts']
        self.assertEqual('123', str(openbts_conf['GSM.Identity.MCC']))

        # Make sure other BTS uses network config
        checkin_response = checkin.CheckinResponder(self.bts2).process(status)
        openbts_conf = checkin_response['config']['openbts']
        self.assertEqual('901', str(openbts_conf['GSM.Identity.MCC']))


class SubsciberCheckinCampedTest(DjangoTestCase):
    """A subscriber's camped status can be updated during a checkin.

    This will update the last_camped and the BTS id of a sub.
    """

    @classmethod
    def setUpClass(cls):
        """Create a User and BTS."""
        cls.username = 'testuser1'
        cls.password = 'testpw!'
        cls.user = models.User(username=cls.username, email='testuser@e.com')
        cls.user.set_password(cls.password)
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        # mock out notifications' celery
        cls.old_celery_app = notifications.celery_app
        notifications.celery_app = mock.MagicMock()

        uuid1 = "59216199-d664-4b7a-a2cb-6f26e9a5d203"
        uuid2 = "0e3e8bbc-1614-11e5-9f31-0124d722f2e0"
        inbound_url = "http://localhost:8090"
        cls.bts1 = models.BTS(
            uuid=uuid1, nickname='bts1', inbound_url=inbound_url,
            secret=uuid1, network=cls.user_profile.network)
        cls.bts1.save()
        cls.bts2 = models.BTS(
            uuid=uuid2, nickname='bts2', inbound_url=inbound_url,
            secret=uuid2, network=cls.user_profile.network)
        cls.bts2.save()
        cls.sub = models.Subscriber(
            network=cls.user_profile.network, bts=cls.bts1,
            imsi='IMSI901550000000001', balance=0)
        cls.sub.save()
        cls.number = models.Number(number='5551234', state="inuse",
                                   network=cls.bts1.network,
                                   kind="number.nexmo.monthly",
                                   subscriber=cls.sub)
        cls.number.save()

    @classmethod
    def tearDownClass(cls):
        """Destroy all the objects we made previously."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts1.delete()
        cls.bts2.delete()
        cls.sub.delete()
        cls.number.delete()
        notifications.celery_app = cls.old_celery_app

    def tearDown(self):
        """Reset the sub last activity."""
        self.sub.last_camped = None
        self.sub.save()

    def test_sub_noactivity(self):
        """Subscriber should start off with no activity."""
        self.assertEqual(self.sub.last_camped, None)

    def test_sub_last_camped(self):
        """Tests to see if subscribers are having last_camped updated."""
        last_seen_datetime = (django.utils.timezone.now() -
                              timedelta(seconds=65))
        self.sub.mark_camped(last_seen_datetime, self.bts1)
        self.assertEqual(last_seen_datetime, self.sub.last_camped)

    def test_sub_last_camped_old(self):
        """Tests to see if we will ignore an older incoming LUR."""
        last_seen_datetime = (django.utils.timezone.now() -
                              timedelta(seconds=65))
        self.sub.mark_camped(last_seen_datetime, self.bts1)
        self.assertEqual(last_seen_datetime, self.sub.last_camped)
        self.sub.mark_camped(
            last_seen_datetime - timedelta(seconds=100), self.bts2)
        self.assertEqual(last_seen_datetime, self.sub.last_camped)
        self.assertEqual(self.bts1, self.sub.bts)

    def test_sub_checkin(self):
        """Towers can checkin and become active."""
        client = APIClient()
        response = client.login(username=self.username, password=self.password)
        req_str = "/api/v1/checkin"
        status_data = {
            'events': [],
            'versions': {
                'endaga': '9.8.7',
                'freeswitch': '8.7.6',
                'gsm': '7.6',
                'python-endaga-core': '6.5.4',
                'python-gsm': '5.4.3',
            },
            'camped_subscribers': [
                {
                    'imsi': 'IMSI901550000000001',
                    'last_seen_secs': '4',
                }
            ]
        }
        data = {
            'bts_uuid': str(self.bts2.uuid),
            'status': json.dumps(status_data)
        }
        response = client.post(req_str, data)
        self.assertEqual(200, response.status_code)
        # Reload BTS object, since DB has been updated.
        self.bts2 = models.BTS.objects.get(id=self.bts2.id)
        # Reload subscriber object from DB since it was changed
        self.sub = models.Subscriber.objects.get(id=self.sub.id)
        self.assertEqual(
            self.bts2.last_active - timedelta(seconds=4),
            self.sub.last_camped)
        self.assertEqual(self.bts2, self.sub.bts)


class CheckinTest(DjangoTestCase):
    """A BTS can checkin.

    It will change status and report its package version numbers.
    """

    @classmethod
    def setUpClass(cls):
        """Create a Network and BTS."""
        cls.network= models.Network.objects.create()
        cls.header = {
            'HTTP_AUTHORIZATION': 'Token %s' % cls.network.api_token
        }

        """Create a User and BTS."""
        cls.username = 'testuser!'
        cls.password = 'testpw!'
        cls.user = models.User(username=cls.username, email='testuser@e.com')
        cls.user.set_password(cls.password)
        cls.user.save()

        # mock out notifications' celery
        cls.old_celery_app = notifications.celery_app
        notifications.celery_app = mock.MagicMock()

        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.uuid = "59216199-d664-4b7a-a2db-6f26e9a5d203"
        inbound_url = "http://localhost:8090"
        cls.bts = models.BTS(
            uuid=cls.uuid, nickname='test-name', inbound_url=inbound_url,
            secret=cls.uuid, network=cls.network, band='GSM900', channel=51)
        cls.bts.save()
        cls.sub = models.Subscriber(
            network=cls.network, bts=cls.bts,
            imsi='IMSI901550000000001', balance=0)
        cls.sub.save()
        cls.number = models.Number(number='5551234', state="inuse",
                                   network=cls.bts.network,
                                   kind="number.nexmo.monthly",
                                   subscriber=cls.sub)
        cls.number.save()


    @classmethod
    def tearDownClass(cls):
        """Destroy all the objects we made previously."""
        cls.network.delete()
        cls.bts.delete()
        cls.sub.delete()
        cls.number.delete()
        models.TimeseriesStat.objects.all().delete()

        notifications.celery_app = cls.old_celery_app

    def setUp(self):
        """Initialize the BTS status."""
        self.bts.last_active = None
        self.bts.status = "no-data"
        self.bts.save()
        self.client = APIClient()
        self.req_str = "/api/v1/checkin"
        self.new_band = 'GSM850'
        self.new_channel = 128
        self.expected_bal = 5000
        self.bal1 = {'p': {'3c470c85': self.expected_bal}, 'n': {'3c470c85': 0}}
        self.status_data = {
            'events': [],
            'uptime': 143,
            'versions': {
                'endaga': '9.8.7',
                'freeswitch': '8.7.6',
                'gsm': '7.6',
                'python-endaga-core': '6.5.4',
                'python-gsm': '5.4.3',
            },
            'camped_subscribers': [{
                'imsi': 'IMSI901550000000001',
                'last_seen_secs': '4'
            }, {
                'imsi': 'IMSI361050000000001',
                'last_seen_secs': '19'
            }],
            'openbts_load': {
                'sdcch_load': 7,
                'sdcch_available': 39,
            },
            'openbts_noise': {
                'noise_rssi_db': -3,
                'ms_target_db': -22,
            },
            'system_utilization': {
                'cpu_percent': 22.2,
                'memory_percent': 33.3,
            },
            'subscribers': {
                'IMSI901550000000001': {
                    'balance': json.dumps(self.bal1),
                    'numbers': ['5551234',],
                },
            },
            #cause radio update
            'radio' : {
                'band' : self.new_band,
                'c0' : self.new_channel,
            }
        }
        self.data = {
            'bts_uuid': str(self.bts.uuid),
        }

    def tearDown(self):
        """Reset the BTS status."""
        self.bts.last_active = None
        self.bts.status = "no-data"
        self.bts.save()

    def test_bts_nodata(self):
        """BTS status should start at 'no-data', and stay that way"""
        prev_up_down_events = models.SystemEvent.objects.filter(
            type__in=['bts up','bts down']).count()
        # Modify timeout for testing
        settings.ENDAGA['BTS_INACTIVE_TIMEOUT_SECS'] = 1
        self.assertEqual(self.bts.status, "no-data")

        # Wait extra time to ensure that timeout can be triggered
        time.sleep(settings.ENDAGA['BTS_INACTIVE_TIMEOUT_SECS'] + 1)
        tasks.downtime_notify()
        self.bts = models.BTS.objects.get(id=self.bts.id)
        self.assertEqual(self.bts.status, "no-data")
        # Check no new up/down events created (for any BTS)
        new_up_down_events = models.SystemEvent.objects.filter(
            type__in=['bts up','bts down']).count()
        self.assertEqual(new_up_down_events, prev_up_down_events)

    def test_bts_active(self):
        """We can set a BTS as active."""
        prev_up_events = models.SystemEvent.objects.filter(bts=self.bts,
            type='bts up').count()
        self.bts.mark_active()
        self.assertEqual(self.bts.status, "active")
        # Check that up event created
        new_up_events = models.SystemEvent.objects.filter(bts=self.bts,
            type='bts up').count()
        self.assertEqual(new_up_events, prev_up_events+1)

    def test_bts_inactive(self):
        """Set a BTS as active then deactivate."""
        prev_down_events = models.SystemEvent.objects.filter(bts=self.bts,
            type='bts down').count()
        # Modify timeout for testing
        NexmoProvider.send = mock.MagicMock()
        settings.ENDAGA['BTS_INACTIVE_TIMEOUT_SECS'] = 1
        self.bts.mark_active()
        self.assertEqual(self.bts.status, "active")

        # Wait extra time to ensure that timeout can be triggered
        time.sleep(settings.ENDAGA['BTS_INACTIVE_TIMEOUT_SECS'] + 1)
        tasks.downtime_notify()
        self.bts = models.BTS.objects.get(id=self.bts.id)
        self.assertEqual(self.bts.status, "inactive")
        # Check that down event created
        new_down_events = models.SystemEvent.objects.filter(bts=self.bts,
            type='bts down').count()
        self.assertEqual(new_down_events, prev_down_events+1)

    def test_bts_checkin(self):
        """Towers can checkin and become active."""
        self.data['status'] = json.dumps(self.status_data),
        response = self.client.post(self.req_str, self.data, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertTrue("ok", response.data['response']['status'])
        # Reload BTS object, since DB has been updated.
        self.bts = models.BTS.objects.get(id=self.bts.id)
        self.assertEqual(self.bts.status, "active")
        # Version data should have been generated and stored as zero-padded
        # strings.
        versions = json.loads(self.bts.package_versions)
        self.assertEqual('00009.00008.00007', versions['endaga_version'])
        self.assertEqual('00008.00007.00006', versions['freeswitch_version'])
        self.assertEqual('00007.00006',
                         versions['gsm_version'])
        self.assertEqual('00006.00005.00004',
                         versions['python_endaga_core_version'])
        self.assertEqual('00005.00004.00003',
                         versions['python_gsm_version'])
        # Reload subscriber object from DB since it was changed
        self.sub = models.Subscriber.objects.get(id=self.sub.id)
        self.assertEqual(
            self.bts.last_active - timedelta(seconds=4),
            self.sub.last_camped)
        # Uptime data should have been captured.
        self.assertEqual(143, self.bts.uptime)
        # TimeseriesStat instances should be created for openbts_load,
        # openbts_noise and system_utilization params.
        self.assertEqual(6, models.TimeseriesStat.objects.count())
        params = [('sdcch_load', 7), ('sdcch_available', 39),
                  ('noise_rssi_db', -3), ('ms_target_db', -22),
                  ('cpu_percent', 22.2), ('memory_percent', 33.3)]
        for key, value in params:
            stat = models.TimeseriesStat.objects.get(key=key)
            self.assertEqual(value, float(stat.value))

        # There should be a subscriber section
        sub_section = response.data['response']['subscribers']
        self.assertTrue(self.sub.imsi in sub_section)
        self.assertEqual(sub_section[self.sub.imsi]['numbers'],
                         self.sub.numbers_as_list())

        # The subscriber should have a balance of 5000
        self.assertEqual(self.expected_bal, self.sub.balance)
        #bands should have been updated
        self.assertEqual(self.new_band, self.bts.band)
        self.assertEqual(self.new_channel, self.bts.channel)

    def test_bad_band_update(self):
        """ cloud nulls out band/channel if bad ones sent in """
        self.status_data['radio']['band'] = 'GSM950' #not real
        self.data['status'] = json.dumps(self.status_data),
        response = self.client.post(self.req_str, self.data, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertTrue("ok", response.data['response']['status'])
        # Reload BTS object, since DB has been updated.
        self.bts = models.BTS.objects.get(id=self.bts.id)
        self.assertEqual(self.bts.status, "active")
        #bands should have been updated to bad values
        self.assertEqual(None, self.bts.band)
        self.assertEqual(None, self.bts.channel)

    def test_missing_band_update(self):
        """ cloud nulls out band/channel if bad ones sent in """
        #little weird here, None means to use the existing band from the database!
        #which is invalid with channel 128
        self.status_data['radio']['band'] = None
        self.data['status'] = json.dumps(self.status_data),
        response = self.client.post(self.req_str, self.data, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertTrue("ok", response.data['response']['status'])
        # Reload BTS object, since DB has been updated.
        self.bts = models.BTS.objects.get(id=self.bts.id)
        #still active
        self.assertEqual(self.bts.status, "active")
        #bands should have been updated to bad values
        self.assertEqual(None, self.bts.band)
        self.assertEqual(None, self.bts.channel)

    def test_bad_channel_update(self):
        """ cloud nulls out band/channel if bad ones sent in """
        self.status_data['radio']['c0'] = 1 #invalid for GSM850
        self.data['status'] = json.dumps(self.status_data),
        response = self.client.post(self.req_str, self.data, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertTrue("ok", response.data['response']['status'])
        # Reload BTS object, since DB has been updated.
        self.bts = models.BTS.objects.get(id=self.bts.id)
        #still active
        self.assertEqual(self.bts.status, "active")
        #bands should have been updated to bad values
        self.assertEqual(None, self.bts.band)
        self.assertEqual(None, self.bts.channel)

    def test_bts_legacy_checkin(self):
        """ Checkin still handles old (openbts-named) checkins """
        """ test if it can handle older names for version tags """
        self.status_data['versions'] = {
            'endaga': '9.8.7',
            'freeswitch': '8.7.6',
            'openbts-public': '7.6',
            'python-endaga-core': '6.5.4',
            'python-openbts': '5.4.3',
        }
        self.data['status'] = json.dumps(self.status_data),
        response = self.client.post(self.req_str, self.data, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertTrue("ok", response.data['response']['status'])
        # Reload BTS object, since DB has been updated.
        self.bts = models.BTS.objects.get(id=self.bts.id)
        #still active
        self.assertEqual(self.bts.status, "active")
        # Version data should have been generated and stored as zero-padded
        # strings.
        versions = json.loads(self.bts.package_versions)
        self.assertEqual('00007.00006',
                         versions['gsm_version'])
        self.assertEqual('00005.00004.00003',
                         versions['python_gsm_version'])

    def test_bts_registration(self):
        """A BTS can register."""
        client = APIClient()
        req_str = "/api/v1/bts/register"
        data = {
            'bts_uuid': str(self.bts.uuid),
            'vpn_status': 'up',
            'vpn_ip': '10.12.13.14',
            'federer_port': '80',
        }
        response = client.get(req_str, data, **self.header)
        self.assertEqual(200, response.status_code)
        self.bts = models.BTS.objects.get(id=self.bts.id)
        self.assertEqual(self.bts.status, "active")
        self.assertEqual(self.bts.inbound_url, "http://10.12.13.14:80")

    def test_bts_registration_old_style(self):
        """A BTS can register."""
        client = APIClient()
        req_str = "/api/v1/bts/register"
        data = {
            'bts_uuid': str(self.bts.uuid),
            'vpn_status': 'up',
            'vpn_ip': '10.12.13.14',
        }
        response = client.get(req_str, data, **self.header)
        self.assertEqual(200, response.status_code)
        self.bts = models.BTS.objects.get(id=self.bts.id)
        self.assertEqual(self.bts.status, "active")
        self.assertEqual(self.bts.inbound_url, "http://10.12.13.14:8081")

    def test_checkin_deregistered_bts(self):
        """A special checkin response is generated for deregistered towers."""
        # Create a new BTS just for this test.
        uuid = "59216199-d664-4b7a-a2db-6f26e9a5d313"
        inbound_url = "http://localhost:8090"
        new_bts = models.BTS(
            uuid=uuid, nickname='test-name', inbound_url=inbound_url,
            secret=uuid, network=self.network)
        new_bts.save()
        # Go through the tower deregistration process -- create a dBTS and
        # delete the BTS model.
        dbts = models.DeregisteredBTS(uuid=new_bts.uuid, secret=new_bts.secret)
        dbts.save()
        new_bts.delete()
        # Post a checkin as the client would do.
        client = APIClient()
        req_str = "/api/v1/checkin"
        status_data = {
            'events': [],
            'uptime': 143,
            'versions': {
                'endaga': '9.8.7',
                'freeswitch': '8.7.6',
                'gsm': 7.6,
                'python-endaga-core': '6.5.4',
                'python-gsm': '5.4.3',
            },
        }
        data = {
            'bts_uuid': str(new_bts.uuid),
            'status': json.dumps(status_data)
        }
        response = client.post(req_str, data, **self.header)
        self.assertEqual(200, response.status_code)
        # Pylint doesn't handle the DRF APIView response.
        # pylint: disable=no-member
        data = response.data['response']
        self.assertEqual('deregistered', data['status'])
        # The deregistered BTS should have been deleted.
        self.assertEqual(0, models.DeregisteredBTS.objects.filter(
            uuid=new_bts.uuid).count())


class ChargeOperatorOnEventCreationTest(TestCase):
    """When local events are created, we should charge the operator."""

    @classmethod
    def setUpClass(cls):
        """Setup some basic objects."""
        cls.user = models.User(username="ab", email="a@b.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.bts = models.BTS(uuid="331111", nickname="test-bts-name",
                             inbound_url="http://localhost/331111/test",
                             network=cls.user_profile.network)
        cls.bts.save()
        cls.subscriber_imsi = 'IMSI000456'
        cls.subscriber = models.Subscriber.objects.create(
            balance=10000, name='test-sub-name', imsi=cls.subscriber_imsi,
            network=cls.bts.network)
        cls.subscriber.save()

    @classmethod
    def tearDownClass(cls):
        """Destroy all the objects we made previously."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.subscriber.delete()

    def setUp(self):
        """Setup the event template.

        Each test can use this template and set a to_number, a kind, and a
        billsec to test different billing outcomes.
        """
        self.event_template = {
            'date': '2015-02-15 15:32:43',
            'imsi': self.subscriber_imsi,
            'oldamt': 10000,
            'newamt': 9000,
            'change': 1000,
            'reason': 'test reason',
            'kind': None,
            'billsec': None,
            'call_duration': 300,
            'from_imsi': 'IMSI000123',
            'from_number': '5550123',
            'to_imsi': 'IMSI000987',
            'to_number': None,
            'tariff': 1000,
            'seq': 3,
        }

    def tearDown(self):
        """Reset the test data."""
        self.bts.max_seqno = 0
        for usage_event in models.UsageEvent.objects.all():
            usage_event.delete()
        self.user_profile.network.ledger.balance = 0
        self.user_profile.network.ledger.save()

    def reload_user_profile(self):
        """Reload the user profile from the DB."""
        self.user_profile = models.UserProfile.objects.get(
            id=self.user_profile.id)

    def test_bill_operator_for_local_sent_sms(self):
        """We can bill operators for local_sms events."""
        # Tweak the local tier's operator cost to make this more interesting.
        tier = models.BillingTier.objects.get(
            network=self.user_profile.network,
            directionality='on_network_send')
        tier.cost_to_operator_per_sms = 1000
        tier.save()
        # Add a new event.
        self.event_template['kind'] = 'local_sms'
        checkin.handle_event(self.bts, self.event_template)
        # The operator's ledger's balance should have a deduction.
        self.reload_user_profile()
        expected_credit = (-1000
                           if self.user_profile.network.billing_enabled
                           else 0)
        self.assertEqual(expected_credit,
                         self.user_profile.network.ledger.balance)

    def test_bill_operator_for_local_received_call(self):
        """We can bill operators for local_recv_call events."""
        self.event_template['to_number'] = ''.join(['855', '9195554433'])
        self.event_template['kind'] = 'local_recv_call'
        self.event_template['billsec'] = 100
        # Tweak the on-network receive tier's operator cost to make this more
        # interesting than the default (zero).
        tier = models.BillingTier.objects.get(
            network=self.user_profile.network,
            directionality='on_network_receive')
        tier.cost_to_operator_per_min = 2000
        tier.save()
        checkin.handle_event(self.bts, self.event_template)
        # The operator's ledger's balance should have a deduction.
        self.reload_user_profile()
        expected_credit = (int(-2000 * 100 / 60.)
                           if self.user_profile.network.billing_enabled
                           else 0)
        self.assertEqual(expected_credit,
                         self.user_profile.network.ledger.balance)


class HandleGPRSEventTest(TestCase):
    """The BTS should be able to process GPRS events."""

    @classmethod
    def setUpClass(cls):
        """Setup a User, BTS and Subscriber."""
        cls.user = models.User(username="vv", email="v@v.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.bts = models.BTS(uuid="88332", nickname="test-bts-name",
                             inbound_url="http://localhost/88332/test",
                             network=cls.user_profile.network)
        cls.bts.save()
        cls.imsi = 'IMSI000553'
        cls.subscriber = models.Subscriber.objects.create(
            balance=20000, name='test-sub-name', imsi=cls.imsi,
            network=cls.bts.network)
        cls.subscriber.save()
        cls.incoming_event = {
            'date': '2015-03-15 13:32:17',
            'imsi': cls.imsi,
            'oldamt': 1000,
            'newamt': 1000,
            'change': 0,
            'reason': 'GPRS usage',
            'kind': 'gprs',
            'up_bytes': 120,
            'down_bytes': 430,
            'timespan': 60,
            'seq': 6,
        }
        checkin.handle_event(cls.bts, cls.incoming_event)
        cls.new_usage_event = models.UsageEvent.objects.all()[0]

    @classmethod
    def tearDownClass(cls):
        """Delete some of the things we created."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.subscriber.delete()
        for usage_event in models.UsageEvent.objects.all():
            usage_event.delete()

    def test_parse_date(self):
        event_date = self.new_usage_event.date.strftime('%Y-%m-%d %H:%M:%S')
        self.assertEqual(self.incoming_event['date'], event_date)

    def test_parse_imsi(self):
        event_imsi = self.new_usage_event.subscriber.imsi
        self.assertEqual(self.incoming_event['imsi'], event_imsi)

    def test_parse_oldamt(self):
        event_oldamt = self.new_usage_event.oldamt
        self.assertEqual(self.incoming_event['oldamt'], event_oldamt)

    def test_parse_newamt(self):
        event_newamt = self.new_usage_event.newamt
        self.assertEqual(self.incoming_event['newamt'], event_newamt)

    def test_parse_change(self):
        event_change = self.new_usage_event.change
        self.assertEqual(self.incoming_event['change'], event_change)

    def test_parse_reason(self):
        event_reason = self.new_usage_event.reason
        self.assertEqual(self.incoming_event['reason'], event_reason)

    def test_parse_kind(self):
        event_kind = self.new_usage_event.kind
        self.assertEqual(self.incoming_event['kind'], event_kind)

    def test_parse_uploaded_bytes(self):
        event_uploaded_bytes = self.new_usage_event.uploaded_bytes
        self.assertEqual(self.incoming_event['up_bytes'],
                         event_uploaded_bytes)

    def test_parse_downloaded_bytes(self):
        event_downloaded_bytes = self.new_usage_event.downloaded_bytes
        self.assertEqual(self.incoming_event['down_bytes'],
                         event_downloaded_bytes)

    def test_parse_timespan(self):
        event_timespan = self.new_usage_event.timespan
        self.assertEqual(self.incoming_event['timespan'], event_timespan)


class PrintableVersionTest(TestCase):
    """Tests models.BTS.printable_version."""

    @classmethod
    def setUpClass(cls):
        cls.user = models.User(username="vv", email="v@v.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.bts = models.BTS(uuid="88332", nickname="test-bts-name",
                             inbound_url="http://localhost/88332/test",
                             network=cls.user_profile.network)
        cls.bts.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.user_profile.delete()
        cls.user_profile.network.delete()
        cls.bts.delete()

    def test_one(self):
        sortable = '00001.00002.00003'
        self.assertEqual('1.2.3', self.bts.printable_version(sortable))

    def test_two(self):
        sortable = '00010.00002.00003'
        self.assertEqual('10.2.3', self.bts.printable_version(sortable))

    def test_three(self):
        sortable = '00010.00000.00030'
        self.assertEqual('10.0.30', self.bts.printable_version(sortable))

    def test_four(self):
        sortable = None
        self.assertEqual(None, self.bts.printable_version(sortable))

    def test_no_micro_version(self):
        sortable = '00021.00030'
        self.assertEqual('21.30', self.bts.printable_version(sortable))

    def test_major_only(self):
        sortable = '00030'
        self.assertEqual('30', self.bts.printable_version(sortable))

    def test_non_int(self):
        """Freeswitch appends other data to their version numbers."""
        sortable = '00001.00004.15~1-1~wheezy+1'
        self.assertEqual('1.4.15~1-1~wheezy+1',
                         self.bts.printable_version(sortable))
