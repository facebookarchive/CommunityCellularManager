"""Testing the NetworkBilling view.

Usage:
  $ python manage.py test endagaweb.NetworkBillingConversionTest

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from django import test

from ccm.common.currency import CURRENCIES
from endagaweb.views import network


class NetworkBillingConversionTest(test.TestCase):
    """Testing the view's ability to convert credits.

    Some day this may be more complex as we take into account the network
    setting for subscriber currency.
    """

    def setUp(self):
        self.view = network.NetworkPrices()

    def test_nominal_conversion(self):
        self.assertEqual(4500, self.view.parse_subscriber_cost('4500').amount)

    def test_negative_value(self):
        with self.assertRaises(ValueError):
            self.view.parse_subscriber_cost('-0.045')
        with self.assertRaises(ValueError):
            self.view.parse_subscriber_cost('-1,000')

    def test_large_number(self):
        """This is testing the max value that is allowed by the DB"""

        # Largest amount in USD
        self.view.parse_subscriber_cost(21474.83647)
        with self.assertRaises(ValueError):
            self.view.parse_subscriber_cost(21474.83648)

        # Largest amount in IDR
        self.view.parse_subscriber_cost(2147483647, CURRENCIES['IDR'])
        with self.assertRaises(ValueError):
            self.view.parse_subscriber_cost(2147483648, CURRENCIES['IDR'])

    def test_bad_string(self):
        with self.assertRaises(ValueError):
            self.view.parse_subscriber_cost('zero-point-five')

    def test_zero(self):
        self.assertEqual(0, self.view.parse_subscriber_cost('0').amount)

    def test_large_integer(self):
        self.assertEqual(15000,
                self.view.parse_subscriber_cost(15000).amount)

    def test_formatted_string(self):
        self.assertEqual(1000,
                self.view.parse_subscriber_cost('1,000').amount)
        self.assertEqual(1000,
                self.view.parse_subscriber_cost('1,000.000').amount)

    def test_bad_formatted_string(self):
        # You can't put the thousands seperator anywhere
        with self.assertRaises(ValueError):
            self.view.parse_subscriber_cost('10,000,00')

        # Decimal point use has to make sense for en_US
        # TODO expand for other locales
        with self.assertRaises(ValueError):
            self.view.parse_subscriber_cost('100.000,00')
