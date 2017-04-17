"""Tests for the web.py federer server.

Usage (from root of the repo):
    $ nosetests core.tests.federer_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""





import unittest

import itsdangerous
import mock
from paste.fixture import TestApp

from core.checkin import CheckinHandler
from core.config_database import ConfigDB
from core.event_store import EventStore
import core.federer
import core.federer_handlers.cdr
import core.federer_handlers.sms_cdr
import core.federer_handlers.config
from core.tests import mocks
from core.subscriber import subscriber
from core.exceptions import SubscriberNotFound


class CallCDRTestCase(unittest.TestCase):
    """Handling call CDRs."""

    @classmethod
    def setUpClass(cls):
        """Load up some pricing data into the config db."""
        price_data = [
            {
                'directionality': 'off_network_send',
                'prefix': '789',
                'country_name': 'Ocenaia',
                'country_code': 'OC',
                'cost_to_subscriber_per_sms': 300,
                'cost_to_subscriber_per_min': 200,
            }, {
                'directionality': 'off_network_receive',
                'cost_to_subscriber_per_sms': 400,
                'cost_to_subscriber_per_min': 100,
            }, {
                'directionality': 'on_network_send',
                'cost_to_subscriber_per_sms': 40,
                'cost_to_subscriber_per_min': 10,
            }, {
                'directionality': 'on_network_receive',
                'cost_to_subscriber_per_sms': 30,
                'cost_to_subscriber_per_min': 40,
            }
        ]
        # Create a simplified checkin response with just price data.
        checkin_response = {
            'config': {
                'prices': price_data
            }
        }
        # Mock the checkin handler object such that validation just returns the
        # object to-be-validated (without checking JWT).
        mock_checkin_handler = CheckinHandler
        mock_checkin_handler.validate = lambda self, data: data
        mock_checkin_handler(checkin_response)

        # mock subscriber so we dont actually execute DB queries
        mock_subscriber = mocks.MockSubscriber()
        cls.original_subscriber = core.federer_handlers.cdr.subscriber
        core.federer_handlers.cdr.subscriber = mock_subscriber

    @classmethod
    def tearDownClass(cls):
        core.federer_handlers.cdr.subscriber = cls.original_subscriber

    def setUp(self):
        self.test_app = TestApp(core.federer.app.wsgifunc())
        self.fixtures_path = 'core/tests/fixtures/'
        self.event_store = EventStore()

    def tearDown(self):
        # Reset the EventStore.
        self.event_store.drop_table()

    def test_get_raises_404(self):
        """Cannot GET to this endpoint."""
        response = self.test_app.get('/cdr', expect_errors=True)
        self.assertEqual(404, response.status)

    def test_post_without_cdr_raises_400(self):
        """Must send CDR data."""
        data = {}
        response = self.test_app.post('/cdr', params=data, expect_errors=True)
        self.assertEqual(400, response.status)

    def test_post_cdr_with_origination_does_not_generate_event(self):
        """CDRs are not processed if they contain an <origination> tag."""
        cdr_path = self.fixtures_path + 'cdr-with-origination.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }
        response = self.test_app.post('/cdr', params=data)
        # We expect to get a 200 OK, but no event will be in the EventStore.
        self.assertEqual(200, response.status)
        self.assertEqual(0, len(self.event_store.get_events()))

    def test_post_cdr_sans_origination_generates_event_with_duration(self):
        """CDRs can be posted to the server and turned into events."""
        cdr_path = self.fixtures_path + 'outside-call-cdr.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }
        # We should be able to successfully send the data to the server.
        response = self.test_app.post('/cdr', params=data)
        self.assertEqual(200, response.status)
        # And the server should have added data to the DB, so we should be able
        # to query for it.  The most recently added event should have a
        # call_duration.
        events = self.event_store.get_events()
        event = events[-1]
        # Get the expected call duration from <call_duration> tag in the CDR.
        expected_call_duration = 67
        self.assertEqual(expected_call_duration, event['call_duration'])
        # Get the expected billsec from <billsec> tag in the CDR.
        expected_billsec = 42
        self.assertEqual(expected_billsec, event['billsec'])

    def test_parse_outside_call_cdr(self):
        """We can extract info from outside_call CDRs."""
        cdr_path = self.fixtures_path + 'outside-call-cdr.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }
        # We can send this info to the server and it should have added data to
        # the DB.
        self.test_app.post('/cdr', params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual('IMSI510555550000071', event['from_imsi'])
        self.assertEqual('6285574719949', event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual('7892395268385', event['to_number'])
        self.assertEqual('outside_call', event['kind'])
        self.assertEqual(200, event['tariff'])

    def test_parse_local_call_cdr(self):
        """We can extract info from local_call CDRs."""
        cdr_path = self.fixtures_path + 'local-call-cdr.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }
        self.test_app.post('/cdr', params=data)
        events = self.event_store.get_events()
        caller_event = events[-2]
        callee_event = events[-1]
        self.assertEqual('IMSI510555550000071', caller_event['from_imsi'])
        self.assertEqual('6285574719949', caller_event['from_number'])
        self.assertEqual('IMSI510555550000081', caller_event['to_imsi'])
        self.assertEqual('6285574719944', caller_event['to_number'])
        self.assertEqual('local_call', caller_event['kind'])
        self.assertEqual(10, caller_event['tariff'])

        self.assertEqual('IMSI510555550000071', callee_event['from_imsi'])
        self.assertEqual('6285574719949', callee_event['from_number'])
        self.assertEqual('IMSI510555550000081', callee_event['to_imsi'])
        self.assertEqual('6285574719944', callee_event['to_number'])
        self.assertEqual('local_recv_call', callee_event['kind'])
        self.assertEqual(40, callee_event['tariff'])

    def test_parse_local_call_msisdn_cdr(self):
        """
        We can extract info from local_call_msisdn CDR which have
        MSISDN as the callee_id_number instead of IMSI.
        """
        cdr_path = self.fixtures_path + 'local-call-msisdn-cdr.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }

        self.test_app.post('/cdr', params=data)
        events = self.event_store.get_events()
        caller_event = events[-2]
        callee_event = events[-1]
        self.assertEqual('IMSI123451234512342', caller_event['from_imsi'])
        self.assertEqual('639360100757', caller_event['from_number'])
        # Check the IMSI value from MockSubscriber's get_imsi_from_number
        self.assertEqual('IMSI000227', caller_event['to_imsi'])
        self.assertEqual('639360100755', caller_event['to_number'])
        self.assertEqual('local_call', caller_event['kind'])
        self.assertEqual(10, caller_event['tariff'])

        self.assertEqual('IMSI123451234512342', callee_event['from_imsi'])
        self.assertEqual('639360100757', callee_event['from_number'])
        # Check the IMSI value from MockSubscriber's get_imsi_from_number
        self.assertEqual('IMSI000227', callee_event['to_imsi'])
        self.assertEqual('639360100755', callee_event['to_number'])
        self.assertEqual('local_recv_call', callee_event['kind'])
        self.assertEqual(40, callee_event['tariff'])

    def test_parse_free_call_cdr(self):
        """We can extract info from free_call CDRs."""
        cdr_path = self.fixtures_path + 'free-call-cdr.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }
        self.test_app.post('/cdr', params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual('IMSI510555550000996', event['from_imsi'])
        self.assertEqual(None, event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual('888', event['to_number'])
        self.assertEqual(0, event['tariff'])

    def test_parse_error_call_cdr(self):
        """We can extract info from error_call CDRs."""
        cdr_path = self.fixtures_path + 'error-call-cdr.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }
        self.test_app.post('/cdr', params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual('IMSI510555550000087', event['from_imsi'])
        self.assertEqual(None, event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual('6281248174025', event['to_number'])
        self.assertEqual(0, event['tariff'])

    def test_parse_incoming_call_cdr(self):
        """ We can extract info from well-formed incoming call CDRs """
        cdr_path = self.fixtures_path + 'incoming-call-cdr.xml'
        with open(cdr_path) as cdr_file:
            data = {
                'cdr': cdr_file.read()
            }
        self.test_app.post('/cdr', params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual(None, event['from_imsi'])
        self.assertEqual('18657194461', event['from_number'])
        self.assertEqual('IMSI901550000000072', event['to_imsi'])
        self.assertEqual('12529178659', event['to_number'])
        self.assertEqual(100, event['tariff'])



class SMSCDRTestCase(unittest.TestCase):
    """Handling SMS CDRs."""

    @classmethod
    def setUpClass(cls):
        """Load up some pricing data into the config db."""
        price_data = [
            {
                'directionality': 'off_network_send',
                'prefix': '789',
                'country_name': 'Ocenaia',
                'country_code': 'OC',
                'cost_to_subscriber_per_sms': 300,
                'cost_to_subscriber_per_min': 200,
            }, {
                'directionality': 'off_network_receive',
                'cost_to_subscriber_per_sms': 400,
                'cost_to_subscriber_per_min': 100,
            }, {
                'directionality': 'on_network_send',
                'cost_to_subscriber_per_sms': 40,
                'cost_to_subscriber_per_min': 10,
            }, {
                'directionality': 'on_network_receive',
                'cost_to_subscriber_per_sms': 30,
                'cost_to_subscriber_per_min': 40,
            }
        ]
        # Create a simplified checkin response with just price data.
        checkin_response = {
            'config': {
                'prices': price_data
            }
        }
        # Mock the checkin handler object such that validation just returns the
        # object to-be-validated (without checking JWT).
        mock_checkin_handler = CheckinHandler
        mock_checkin_handler.validate = lambda self, data: data
        mock_checkin_handler(checkin_response)

        # mock subscriber so we dont actually execute DB queries
        mock_subscriber = mocks.MockSubscriber()
        cls.original_subscriber = core.federer_handlers.sms_cdr.subscriber
        core.federer_handlers.sms_cdr.subscriber = mock_subscriber

    @classmethod
    def tearDownClass(cls):
        core.federer_handlers.sms_cdr.subscriber = cls.original_subscriber

    def setUp(self):
        self.test_app = TestApp(core.federer.app.wsgifunc())
        self.endpoint = '/smscdr'
        self.event_store = EventStore()

    def tearDown(self):
        # Reset the EventStore.
        self.event_store.drop_table()

    def test_get(self):
        """Cannot GET to this endpoint."""
        response = self.test_app.get(self.endpoint, expect_errors=True)
        self.assertEqual(405, response.status)

    def test_post_without_data_raises_400(self):
        """Must send some data."""
        data = {}
        response = self.test_app.post(self.endpoint, params=data,
                                      expect_errors=True)
        self.assertEqual(400, response.status)

    def test_post_with_data_generates_event(self):
        data = {
            'from_name': 'IMSI901550000000084',
            'from_number': '12345',
            'service_type': 'local_sms',
            'destination': '5551234',
        }
        response = self.test_app.post(self.endpoint, params=data)
        self.assertEqual(200, response.status)
        # Local SMS will actually generate two events -- one for the sender and
        # one for the recipient.
        self.assertEqual(2, len(self.event_store.get_events()))

    def test_local_sms(self):
        """We should set event info when sending local_sms."""
        data = {
            'from_name': 'IMSI000234',
            'from_number': '12345',
            'service_type': 'local_sms',
            'destination': '5552345',
        }
        self.test_app.post(self.endpoint, params=data)
        events = self.event_store.get_events()
        event = events[-1]
        # TODO(matt): do we really not have the from_number?
        # XXX(omar): apparently it is required else tests fail
        self.assertEqual(data['from_name'], event['from_imsi'])
        self.assertEqual(data['from_number'], event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual(data['destination'], event['to_number'])
        self.assertEqual(30, event['tariff'])
        # TODO(matt): check that the recipient was also billed.

    def test_outside_sms(self):
        """We should set event info when sending outside_sms."""
        data = {
            'from_name': 'IMSI000345',
            'from_number': '12345',
            'service_type': 'outside_sms',
            'destination': '7895551234',
        }
        self.test_app.post(self.endpoint, params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual(data['from_name'], event['from_imsi'])
        self.assertEqual(data['from_number'], event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual(data['destination'], event['to_number'])
        self.assertEqual(300, event['tariff'])

    def test_free_sms(self):
        """We should set event info when sending free_sms."""
        data = {
            'from_name': 'IMSI000111',
            'from_number': '12345',
            'service_type': 'free_sms',
            'destination': '5552888',
        }
        self.test_app.post(self.endpoint, params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual(data['from_name'], event['from_imsi'])
        self.assertEqual(data['from_number'], event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual(data['destination'], event['to_number'])
        self.assertEqual(0, event['tariff'])

    def test_incoming_sms(self):
        """We should set event info when sending incoming_sms.

        TODO(matt): I think this test is misleading because we do not post
                    incoming_sms events to /smscdr in the real app.  These
                    messages go to federer_handlers.sms.endaga_sms.
        """
        data = {
            'from_name': 'IMSI000333',
            'from_number': '12345',
            'service_type': 'incoming_sms',
            'destination': '5554433',
        }
        self.test_app.post(self.endpoint, params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual(data['from_name'], event['from_imsi'])
        self.assertEqual(data['from_number'], event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual(data['destination'], event['to_number'])
        self.assertEqual(400, event['tariff'])

    def test_error_sms(self):
        """We should set event info when sending error_sms."""
        data = {
            'from_name': 'IMSI000889',
            'from_number': '12345',
            'service_type': 'error_sms',
            'destination': '5556411',
        }
        self.test_app.post(self.endpoint, params=data)
        events = self.event_store.get_events()
        event = events[-1]
        self.assertEqual(data['from_name'], event['from_imsi'])
        self.assertEqual(data['from_number'], event['from_number'])
        self.assertEqual(None, event['to_imsi'])
        self.assertEqual(data['destination'], event['to_number'])
        self.assertEqual(0, event['tariff'])


class DeactivateNumberTest(unittest.TestCase):
    """Testing the number deactivation command endpoint.

    We use a federer config endpoint to send number-deactivation commands to
    the BTS immediately (as opposed to sending data in a checkin-response).
    """

    @classmethod
    def setUpClass(cls):
        """Setup the test app."""
        cls.test_app = TestApp(core.federer.app.wsgifunc())
        cls.endpoint = '/config/deactivate_number'
        # Setup a serializer so we can send signed data.  Bootstrap the secret.
        config_db = ConfigDB()
        config_db['bts_secret'] = 'yup'
        cls.serializer = itsdangerous.JSONWebSignatureSerializer(
            config_db['bts_secret'])

    def test_get(self):
        """Cannot GET to this endpoint."""
        response = self.test_app.get(self.endpoint, expect_errors=True)
        self.assertEqual(404, response.status)

    def test_post_sans_params(self):
        """Cannot POST to this endpoint without the right params."""
        data = {}
        response = self.test_app.post(self.endpoint, params=data,
                                      expect_errors=True)
        self.assertEqual(400, response.status)

    def test_post_bad_jwt(self):
        """An invalid jwt causes a failure."""
        data = {
            'jwt': 'invalid'
        }
        response = self.test_app.post(self.endpoint, params=data,
                                      expect_errors=True)
        self.assertEqual(400, response.status)

    def test_post_with_nonexistent_number(self):
        """Sending a nonexistent number raises 404."""
        data = {
            'number': '5551234',
        }
        signed_data = {
            'jwt': self.serializer.dumps(data),
        }
        # Monkeypatch the imsi/number lookup, in this case making the lookup
        # fail.
        def mock_lookup(_):
            raise SubscriberNotFound
        original_lookup = core.federer_handlers.config.subscriber.get_imsi_from_number
        core.federer_handlers.config.subscriber.get_imsi_from_number = mock_lookup
        response = self.test_app.post(self.endpoint, params=signed_data,
                                      expect_errors=True)
        self.assertEqual(404, response.status)
        # Repair the monkeypatch.
        core.federer_handlers.config.subscriber.get_imsi_from_number = original_lookup

    def test_deactivate(self):
        """Sending valid params will deactivate a number."""
        data = {
            'number': '5551234',
        }
        signed_data = {
            'jwt': self.serializer.dumps(data),
        }
        # Monkeypatch the imsi/number lookup, in this case making the lookup
        # succeed.
        def mock_lookup(_):
            return 'IMSI901550000000084'
        original_lookup = core.federer_handlers.config.subscriber.get_imsi_from_number
        core.federer_handlers.config.subscriber.get_imsi_from_number = mock_lookup
        with mock.patch('core.federer_handlers.config.subscriber.delete_number') as mocked_delete:
            response = self.test_app.post(self.endpoint, params=signed_data)
            # The mocked deletion should've been called with certain args, and the
            # server should reply with 200 OK.
            self.assertEqual(200, response.status)
            self.assertTrue(mocked_delete.called)
            args, _ = mocked_delete.call_args
            imsi, number = args
            self.assertEqual('IMSI901550000000084', imsi)
            self.assertEqual('5551234', number)
        # Repair the monkeypatch.
        core.federer_handlers.config.subscriber.get_imsi_from_number = original_lookup

    def test_deactivate_last_number(self):
        """Sending valid params will fail if it's the sub's last number."""
        data = {
            'number': '5551234',
        }
        signed_data = {
            'jwt': self.serializer.dumps(data),
        }
        # Monkeypatch the imsi/number lookup, in this case making the lookup
        # succeed.
        def mock_lookup(_):
            return 'IMSI901550000000084'
        original_lookup = core.federer_handlers.config.subscriber.get_imsi_from_number
        core.federer_handlers.config.subscriber.get_imsi_from_number = mock_lookup
        # Monkeypatch the number deletion, making it raise a ValueError, as
        # though this were the sub's last number.
        def mock_delete(imsi, number):
            raise ValueError
        original_delete = core.federer_handlers.config.subscriber.delete_number
        core.federer_handlers.config.subscriber.delete_number = mock_delete
        response = self.test_app.post(self.endpoint, params=signed_data,
                                      expect_errors=True)
        # The request should fail.
        self.assertEqual(400, response.status)
        # Repair the monkeypatches.
        core.federer_handlers.config.subscriber.get_imsi_from_number = original_lookup
        core.federer_handlers.config.subscriber.delete_number = original_delete


class DeactivateSubscriberTest(unittest.TestCase):
    """Testing the subscriber deactivation command endpoint.

    We use a federer config endpoint to send subscriber-deactivation commands
    to the BTS immediately (as opposed to sending data in a checkin-response).
    """

    @classmethod
    def setUpClass(cls):
        """Setup the test app."""
        cls.test_app = TestApp(core.federer.app.wsgifunc())
        cls.endpoint = '/config/deactivate_subscriber'
        # Setup a serializer so we can send signed data.  Bootstrap the secret.
        config_db = ConfigDB()
        config_db['bts_secret'] = 'yup'
        cls.serializer = itsdangerous.JSONWebSignatureSerializer(
            config_db['bts_secret'])

    def test_get(self):
        """Cannot GET to this endpoint."""
        response = self.test_app.get(self.endpoint, expect_errors=True)
        self.assertEqual(404, response.status)

    def test_post_sans_params(self):
        """Cannot POST to this endpoint without the right params."""
        data = {}
        response = self.test_app.post(self.endpoint, params=data,
                                      expect_errors=True)
        self.assertEqual(400, response.status)

    def test_post_bad_jwt(self):
        """An invalid jwt causes a failure."""
        data = {
            'jwt': 'invalid'
        }
        response = self.test_app.post(self.endpoint, params=data,
                                      expect_errors=True)
        self.assertEqual(400, response.status)

    def test_post_with_nonexistent_imsi(self):
        """Sending a nonexistent imsi raises 404."""
        data = {
            'imsi': 'IMSI000555',
        }
        signed_data = {
            'jwt': self.serializer.dumps(data),
        }
        # Monkeypatch the imsi/number lookup, in this case making the lookup
        # fail.
        def mock_delete(_):
            raise SubscriberNotFound
        original_lookup = core.federer_handlers.config.subscriber.delete_subscriber
        core.federer_handlers.config.subscriber.delete_subscriber = mock_delete
        response = self.test_app.post(self.endpoint, params=signed_data,
                                      expect_errors=True)
        self.assertEqual(404, response.status)
        # Repair the monkeypatch.
        core.federer_handlers.config.subscriber.delete_subscriber = original_lookup

    def test_deactivate(self):
        """Sending valid params will deactivate a subscriber.

        All associated numbers will also be deactivated.
        """
        data = {
            'imsi': 'IMSI901550000000084',
        }
        signed_data = {
            'jwt': self.serializer.dumps(data),
        }
        # Monkeypatch the imsi/number lookup, in this case making the lookup
        # succeed.
        def mock_lookup(_):
            return [{'name': 'test'}]
        original_lookup = core.federer_handlers.config.subscriber.get_caller_id
        core.federer_handlers.config.subscriber.get_caller_id = mock_lookup
        with mock.patch('core.federer_handlers.config.subscriber.delete_subscriber') as mocked_delete:
            response = self.test_app.post(self.endpoint, params=signed_data)
        # The mocked deletion should've been called with certain args, and the
        # server should reply with 200 OK.
        self.assertTrue(mocked_delete.called)
        args, _ = mocked_delete.call_args
        imsi = args[0]
        self.assertEqual('IMSI901550000000084', imsi)
        self.assertEqual(200, response.status)
        # Repair the monkeypatch.
        core.federer_handlers.config.subscriber.get_caller_id = original_lookup
