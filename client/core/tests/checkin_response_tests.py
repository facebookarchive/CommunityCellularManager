"""Tests for processing checkin responses.

Usage:
    $ nosetests core.tests.checkin_response_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import copy
import json
import unittest

import mock

from ccm.common import crdt
from core import config_database
from core.billing import process_prices
from core.bts import bts
from core.checkin import CheckinHandler
from core.subscriber import subscriber
from core.subscriber.base import SubscriberNotFound


class PricesTest(unittest.TestCase):
    """We can parse and store pricing data."""

    @classmethod
    def setUpClass(cls):
        # Setup the price data to be processed.  We will process the data once
        # in this setUpClass method and then make assertions on the results in
        # the tests.
        price_data = [
            {
                'directionality': 'off_network_send',
                'prefix': '509',
                'country_name': 'Haiti',
                'country_code': 'HT',
                'cost_to_subscriber_per_sms': 900,
                'cost_to_subscriber_per_min': 1100,
            }, {
                'directionality': 'off_network_send',
                'prefix': '56',
                'country_name': 'Chile',
                'country_code': 'CL',
                'cost_to_subscriber_per_sms': 1000,
                'cost_to_subscriber_per_min': 800,
            }, {
                'directionality': 'off_network_receive',
                'cost_to_subscriber_per_sms': 200,
                'cost_to_subscriber_per_min': 100,
            }, {
                'directionality': 'on_network_send',
                'cost_to_subscriber_per_sms': 30,
                'cost_to_subscriber_per_min': 40,
            }, {
                'directionality': 'on_network_receive',
                'cost_to_subscriber_per_sms': 10,
                'cost_to_subscriber_per_min': 20,
            }
        ]

        # Setup a config db connection.
        cls.config_db = config_database.ConfigDB()
        # Populate the config db with prices
        process_prices(price_data, cls.config_db)

    def test_on_receive(self):
        """On-network receive prices are saved in the config db."""
        key = 'prices.on_network_receive.cost_to_subscriber_per_sms'
        self.assertEqual(10, self.config_db[key])
        key = 'prices.on_network_receive.cost_to_subscriber_per_min'
        self.assertEqual(20, self.config_db[key])

    def test_off_receive(self):
        """Off-network receive prices are saved in the config db."""
        key = 'prices.off_network_receive.cost_to_subscriber_per_sms'
        self.assertEqual(200, self.config_db[key])
        key = 'prices.off_network_receive.cost_to_subscriber_per_min'
        self.assertEqual(100, self.config_db[key])

    def test_on_send(self):
        """On-network send prices are saved in the config db."""
        key = 'prices.on_network_send.cost_to_subscriber_per_sms'
        self.assertEqual(30, self.config_db[key])
        key = 'prices.on_network_send.cost_to_subscriber_per_min'
        self.assertEqual(40, self.config_db[key])

    def test_off_send_prefix_56(self):
        """Off-network send prices for prefix 56 are saved in the config db."""
        key = 'prices.off_network_send.56.cost_to_subscriber_per_sms'
        self.assertEqual(1000, self.config_db[key])
        key = 'prices.off_network_send.56.cost_to_subscriber_per_min'
        self.assertEqual(800, self.config_db[key])

    def test_off_send_prefix_509(self):
        """Off-network send prices for prefix 509 are saved."""
        key = 'prices.off_network_send.509.cost_to_subscriber_per_sms'
        self.assertEqual(900, self.config_db[key])
        key = 'prices.off_network_send.509.cost_to_subscriber_per_min'
        self.assertEqual(1100, self.config_db[key])


class DeregisterTest(unittest.TestCase):
    """We can parse deregistration commands in the checkin response."""

    @classmethod
    def setUpClass(cls):
        # Setup a connection to the config db.
        cls.config_db = config_database.ConfigDB()
        # Set the ConfigDB's secret.
        cdb = config_database.ConfigDB()
        secret = 'ok'
        cdb['bts_secret'] = secret
        # Create a simplified checkin response with just status info.
        cls.checkin_response_template = {
            'status': '',
        }

    def test_deregister(self):
        """Test a deregistration."""
        self.checkin_response_template['status'] = 'deregistered'
        checkin_response = json.dumps(
            {'response': self.checkin_response_template})
        with mock.patch('core.registration.reset_registration') as mock_reset:
            CheckinHandler(checkin_response)
        self.assertTrue(mock_reset.called)

    def test_nominal(self):
        """Things should proceed as normal when status is just 'ok'."""
        self.checkin_response_template['status'] = 'ok'
        checkin_response = json.dumps(
            {'response': self.checkin_response_template})
        with mock.patch('core.registration.reset_registration') as mock_reset:
            CheckinHandler(checkin_response)
        self.assertFalse(mock_reset.called)


class SubscriberUpdateTest(unittest.TestCase):
    """ Can can parse and update subscriber data. """
    def setUp(self):
        self.checkin_response = {
            'response': {
                'subscribers': {}
            }
        }

        # handcrafted, artisinal PNCounters
        bal1 = {'p': {'3c470c85': 5000}, 'n': {'3c470c85': 0}}
        bal2 = {'p': {'26e7cbac': 15000}, 'n': {'26e7cbac': 5000}}

        self.sub1 = 'IMSI000112222233333'
        self.sub2 = 'IMSI000112222244444'

        self.sub_section = {
            self.sub1: {
                'numbers': ['123456'],
                'balance': bal1,
            },
            self.sub2: {
                'numbers': ['765432'],
                'balance': bal2,
            }
        }

        self.config_db = config_database.ConfigDB()

    def tearDown(self):
        for s in self.sub_section:
            # ignore SubscriberNotFound
            try:
                subscriber.delete_subscriber(s)
            except SubscriberNotFound:
                pass

    def test_blank_section(self):
        subs_pre = subscriber.get_subscribers()
        CheckinHandler(json.dumps(self.checkin_response))
        subs_post = subscriber.get_subscribers()
        self.assertTrue(len(subs_pre) == 0)
        self.assertTrue(len(subs_post) == 0)

    def test_sub_add(self):
        subs_pre = subscriber.get_subscribers()
        self.checkin_response['response']['subscribers'] = self.sub_section
        CheckinHandler(json.dumps(self.checkin_response))
        subs_post = subscriber.get_subscriber_states()
        self.assertTrue(len(subs_pre) == 0)
        self.assertTrue(len(subs_post) == 2)
        for sub in self.sub_section:
            e_bal = crdt.PNCounter.from_state(self.sub_section[sub]['balance']).value()
            actual_bal = crdt.PNCounter.from_state(json.loads(subs_post[sub]['balance'])).value()
            self.assertEqual(e_bal, actual_bal)

    def test_sub_remove(self):
        self.checkin_response['response']['subscribers'] = self.sub_section
        CheckinHandler(json.dumps(self.checkin_response))
        subs_pre = subscriber.get_subscribers()
        self.assertTrue(len(subs_pre) == 2)

        sub_section = copy.deepcopy(self.sub_section)
        del(sub_section[self.sub2])
        self.checkin_response['response']['subscribers'] = sub_section
        CheckinHandler(json.dumps(self.checkin_response))
        subs_post = subscriber.get_subscriber_states()
        self.assertTrue(len(subs_post) == 1)

    def test_sub_update(self):
        self.test_sub_add() # sub1 has 5k credit
        subscriber.subtract_credit(self.sub1, 1000) #sub1 spends 1k

        # Do another checkin
        self.checkin_response['response']['subscribers'] = self.sub_section
        CheckinHandler(json.dumps(self.checkin_response))
        subs_post = subscriber.get_subscriber_states()
        bal = crdt.PNCounter.from_state(json.loads(subs_post[self.sub1]['balance'])).value()
        self.assertEqual(4000, bal)

        # simulate cloud adds 11k credits, total should be 15k next checkin
        self.sub_section[self.sub1]['balance']['p']['3c470c85'] += 11000

        # Do another checkin
        self.checkin_response['response']['subscribers'] = self.sub_section
        CheckinHandler(json.dumps(self.checkin_response))
        subs_post = subscriber.get_subscriber_states()
        bal = crdt.PNCounter.from_state(json.loads(subs_post[self.sub1]['balance'])).value()
        self.assertEqual(15000, bal)

        # simulate cloud adds 10k credits, client spends 5k
        # total should be 20k next checkin
        self.sub_section[self.sub1]['balance']['p']['3c470c85'] += 10000
        subscriber.subtract_credit(self.sub1, 5000)

        # Do another checkin
        self.checkin_response['response']['subscribers'] = self.sub_section
        CheckinHandler(json.dumps(self.checkin_response))
        subs_post = subscriber.get_subscriber_states()
        bal = crdt.PNCounter.from_state(json.loads(subs_post[self.sub1]['balance'])).value()
        self.assertEqual(20000, bal)

class AutoupgradeTest(unittest.TestCase):
    """We can parse and store autoupgrade data."""

    @classmethod
    def setUpClass(cls):
        # Setup the autoupgrade data to be processed.  We will process the data
        # once in this setUpClass method and then make assertions on the
        # results in the tests.
        checkin_response = json.dumps({
            'response': {
                'config': {
                    'autoupgrade': {
                        'enabled': True,
                        'channel': 'beta',
                        'in_window': True,
                        'window_start': '02:30:00',
                        'latest_stable_version': '4.3.21',
                        'latest_beta_version': '8.7.65',
                    },
                },
            }
        })
        # Send the checkin response data for processing.
        CheckinHandler(checkin_response)
        # Setup a config db connection.
        cls.config_db = config_database.ConfigDB()

    def test_enabled(self):
        """Enabled/disabled preferences should be saved in the ConfigDB."""
        self.assertEqual(True, self.config_db['autoupgrade.enabled'])

    def test_channel(self):
        """Repo channel preferences should be saved."""
        self.assertEqual('beta', self.config_db['autoupgrade.channel'])

    def test_in_window(self):
        """Save whether or not to upgrade immediately or in a window."""
        self.assertEqual(True, self.config_db['autoupgrade.in_window'])

    def test_window_start(self):
        """Autoupgrade start window prefs should be saved."""
        self.assertEqual('02:30:00',
                         self.config_db['autoupgrade.window_start'])

    def test_latest_versions(self):
        """We save the latest available metapackage package versions."""
        self.assertEqual('4.3.21',
                         self.config_db['autoupgrade.latest_stable_version'])
        self.assertEqual('8.7.65',
                         self.config_db['autoupgrade.latest_beta_version'])


class ConfigBTSTest(unittest.TestCase):
    """We can parse and apply BTS configuration data."""

    def test_arfcn_parameter(self):
        """ A recognised parameter results in the associated method call. """
        checkin_response = json.dumps({
            'response': {
                'config': {
                    'openbts': {
                        'GSM.Radio.C0': 55,
                    },
                },
            }
        })

        with mock.patch.object(bts, 'set_arfcn_c0') as set_arfcn:
            # Send the checkin response data for processing.
            CheckinHandler(checkin_response)
            set_arfcn.assert_called_once_with(55)


    def test_band_parameter(self):
        """ A recognised parameter results in the associated method call. """
        checkin_response = json.dumps({
            'response': {
                'config': {
                    'openbts': {
                        'GSM.Radio.Band': 'GSM850',
                    },
                },
            }
        })

        with mock.patch.object(bts, 'set_band') as set_band:
            # Send the checkin response data for processing.
            CheckinHandler(checkin_response)
            set_band.assert_called_once_with('GSM850')

    def test_invalid_parameter(self):
        """ Unhandled configuration parameter logs an error. """
        checkin_response = json.dumps({
            'response': {
                'config': {
                    'openbts': {
                        'Invalid.Parameter': True,
                    },
                },
            }
        })

        with mock.patch('core.bts.base.logger') as logger:
            # Send the checkin response data for processing.
            CheckinHandler(checkin_response)
            self.assertTrue(logger.error.called)
