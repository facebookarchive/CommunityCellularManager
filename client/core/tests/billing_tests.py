"""Tests for core.billing.

Run this test from the project root
    $ nosetests core.tests.billing_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import unittest
import random
import math

from core.billing import get_call_cost
from core.billing import get_prefix_from_number
from core.billing import get_sms_cost
from core.billing import process_prices
from core.billing import round_to_billable_unit
from core.billing import round_up_to_nearest_100
from core import config_database

TARIFF = 100


class GetCostTest(unittest.TestCase):
    """Testing core.billing.get_call_cost."""

    @classmethod
    def setUpClass(cls):
        # Setup the config db.
        cls.config_db = config_database.ConfigDB()
        cls.config_db['bts_secret'] = 'hokay'
        cls.config_db['free_seconds'] = '5'
        cls.config_db['billable_unit'] = '1'
        # Setup some price data like what would be sent back from the cloud.
        price_data = [
            {
                'directionality': 'off_network_send',
                'prefix': '509',
                'country_name': 'Haiti',
                'country_code': 'HT',
                'cost_to_subscriber_per_sms': 900,
                'cost_to_subscriber_per_min': 1100,
                'billable_unit': 1,
            }, {
                'directionality': 'off_network_send',
                'prefix': '56',
                'country_name': 'Chile',
                'country_code': 'CL',
                'cost_to_subscriber_per_sms': 1000,
                'cost_to_subscriber_per_min': 800,
                'billable_unit': 1,
            }, {
                'directionality': 'off_network_send',
                'prefix': '63',
                'country_name': 'Philippines',
                'country_code': 'PH',
                'cost_to_subscriber_per_sms': 100,
                'cost_to_subscriber_per_min': 600,
                'billable_unit': 30,
            }, {
                'directionality': 'off_network_receive',
                'cost_to_subscriber_per_sms': 200,
                'cost_to_subscriber_per_min': 100,
                'billable_unit': 1,
            }, {
                'directionality': 'on_network_send',
                'cost_to_subscriber_per_sms': 400,
                'cost_to_subscriber_per_min': 300,
                'billable_unit': 1,
            }, {
                'directionality': 'on_network_receive',
                'cost_to_subscriber_per_sms': 500,
                'cost_to_subscriber_per_min': 200,
                'billable_unit': 1,
            }
        ]
        # Populate the config db with prices
        process_prices(price_data, cls.config_db)

    def test_on_receive_call(self):
        """We can get the subscriber price for an on-network received call."""
        billable_seconds = 170
        # Recall that the expected cost is rounded to the nearest value of 100.
        expected_cost = 600
        self.assertEqual(expected_cost,
                         get_call_cost(billable_seconds, 'on_network_receive'))

    def test_on_receive_sms(self):
        """We can get the subscriber price for an on-network received SMS."""
        expected_cost = 500
        self.assertEqual(expected_cost, get_sms_cost('on_network_receive'))

    def test_off_receive_call(self):
        """We can get the subscriber price for an off-network received call."""
        billable_seconds = 700
        expected_cost = 1200
        self.assertEqual(
            expected_cost,
            get_call_cost(billable_seconds, 'off_network_receive'))

    def test_off_receive_sms(self):
        """We can get the subscriber price for an off-network received SMS."""
        expected_cost = 200
        self.assertEqual(expected_cost, get_sms_cost('off_network_receive'))

    def test_on_send_call(self):
        """We can get the subscriber price for an on-network sent call."""
        billable_seconds = 190
        expected_cost = 1000
        self.assertEqual(expected_cost,
                         get_call_cost(billable_seconds, 'on_network_send'))

    def test_on_send_sms(self):
        """We can get the subscriber price for an on-network sent SMS."""
        expected_cost = 400
        self.assertEqual(expected_cost, get_sms_cost('on_network_send'))

    def test_call_to_chile(self):
        """We can get the cost of a call to Chile."""
        billable_seconds = 830
        expected_cost = 11000
        number = ''.join(['56', '1235554567'])
        actual_cost = get_call_cost(billable_seconds, 'off_network_send',
                                    destination_number=number)
        self.assertEqual(expected_cost, actual_cost)

    def test_sms_to_chile(self):
        """We can get the price to a subscriber of an SMS sent to Chile."""
        expected_cost = 1000
        number = ''.join(['56', '1235554567'])
        actual_cost = get_sms_cost('off_network_send',
                                   destination_number=number)
        self.assertEqual(expected_cost, actual_cost)

    def test_call_to_ph(self):
        """ We bill for calls to PH correctly. """
        billable_seconds = 70
        expected_cost = 900
        number = ''.join(['63', '5551234567'])
        actual_cost = get_call_cost(billable_seconds, 'off_network_send',
                                    destination_number=number)
        self.assertEqual(expected_cost, actual_cost)

    def test_nonexistent_prefix(self):
        """If the prefix doesn't exist, it's free.

        The prefix price key might not exist if, say, the billing tier data
        has not yet been loaded.
        """
        expected_cost = 0
        number = ''.join(['9999', '1235554567'])
        actual_cost = get_sms_cost('off_network_send',
                                   destination_number=number)
        self.assertEqual(expected_cost, actual_cost)


class GetPrefixFromNumberTest(unittest.TestCase):
    """Testing core.billing.get_prefix_from_number."""
    @classmethod
    def setUpClass(cls):
        # Setup the config db.
        cls.config_db = config_database.ConfigDB()
        cls.config_db['bts_secret'] = 'yup'
        # Load up some pricing data into the config db.  We use this data to
        # determine what prefixes are available.
        # 2015dec9(shasan): This is a legacy billing response, lacking billable
        # units. This also tests we can handle that case.
        price_data = [
            {
                'directionality': 'off_network_send',
                'prefix': '789',
                'country_name': 'Ocenaia',
                'country_code': 'OC',
                'cost_to_subscriber_per_sms': 300,
                'cost_to_subscriber_per_min': 20,
            }, {
                'directionality': 'off_network_send',
                'prefix': '78',
                'country_name': 'Eurasia',
                'country_code': 'EU',
                'cost_to_subscriber_per_sms': 400,
                'cost_to_subscriber_per_min': 10,
            }, {
                'directionality': 'off_network_send',
                'prefix': '7',
                'country_name': 'Eastasia',
                'country_code': 'EA',
                'cost_to_subscriber_per_sms': 500,
                'cost_to_subscriber_per_min': 30,
            }, {
                'directionality': 'off_network_send',
                'prefix': '3',
                'country_name': 'London',
                'country_code': 'LN',
                'cost_to_subscriber_per_sms': 5000,
                'cost_to_subscriber_per_min': 3000,
            }
        ]
        # Populate the config db with prices
        process_prices(price_data, cls.config_db)

    def test_get_one_digit_prefix(self):
        """We can get a one digit prefix."""
        number = ''.join(['7', '1235557890'])
        self.assertEqual('7', get_prefix_from_number(number))

    def test_get_two_digit_prefix(self):
        """We can get a two digit prefix."""
        number = ''.join(['78', '1235557890'])
        self.assertEqual('78', get_prefix_from_number(number))

    def test_get_three_digit_prefix(self):
        """We can get a three digit prefix."""
        number = ''.join(['789', '1235557890'])
        self.assertEqual('789', get_prefix_from_number(number))

    def test_get_one_digit_uncommon_prefix(self):
        """We can get a one digit uncommon prefix."""
        number = ''.join(['3', '1235557890'])
        self.assertEqual('3', get_prefix_from_number(number))


class RoundCostToBillableUnit(unittest.TestCase):
    """Testing core.billing.round_to_billable_unit."""

    def test_billable_unit_rounding_sans_free_seconds(self):
        for i in range(100):
            billsec = random.randint(1, 5000)
            expected_cost = int(billsec * (TARIFF / 60.0))
            print('%s seconds should cost %s' % (billsec, expected_cost))
            self.assertEqual(expected_cost,
                             round_to_billable_unit(billsec, TARIFF))

    def test_billable_unit_rounding_with_free_seconds(self):
        for i in range(100):
            billsec = random.randint(100, 5000)
            free = random.randint(1, 100)
            expected_cost = int((billsec - free) * (TARIFF / 60.0))
            print('%s seconds with %s free should cost %s' %
                  (billsec, free, expected_cost))
            self.assertEqual(expected_cost,
                             round_to_billable_unit(billsec, TARIFF, free))

    def test_billable_unit_rounding_with_units(self):
        """Test the "rows" of this table: (billsec, expected_cost)."""
        tests = [
            # base case
            (0, 60, 0, 30, 0),
            # call too short
            (5, 60, 0, 30, 30),
            # changing the units
            (5, 60, 0, 60, 60),
            # call slightly too long
            (61, 60, 0, 60, 120),
            # weird non-uniform per minute
            (61, 72, 0, 30, 108),
            # including free seconds
            (61, 60, 10, 60, 60)
        ]
        for test in tests:
            billsec = test[0]
            rate = test[1]
            free = test[2]
            unit = test[3]
            expected_cost = test[4]
            actual_cost = round_to_billable_unit(billsec, rate, free, unit)
            print('%s sec with %s free and a unit of %s sec '
                  'expected cost %s, actual cost %s' %
                  (billsec, free, unit, expected_cost, actual_cost))
            self.assertEqual(expected_cost, actual_cost)


class RoundCostUpToNearest100(unittest.TestCase):
    """Testing core.billing.round_up_to_nearest_100."""

    def test_round_negatives(self):
        # test negatives
        for i in [-10000, -100, -1]:
            self.assertEqual(0, round_up_to_nearest_100(i))

    def test_round_positives(self):
        for i in range(0, 5000):
            self.assertEqual(int(math.ceil(i / float(100))) * 100,
                             round_up_to_nearest_100(i))
