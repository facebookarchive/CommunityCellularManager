"""
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
from sys import version_info
from unittest import TestCase

from .. import Money, CURRENCIES, humanize_credits, parse_credits

TEST_LONG_VALUES = (version_info[0] == 2)  # no long ints in Python 3

class MoneyTestCase(TestCase):

    def test_init_money_with_ints(self):
        self.assertEqual(repr(Money(10)), "$10.00")
        if TEST_LONG_VALUES:
            self.assertEqual(
                repr(Money(long(10000))),  # noqa: F821
                "$10,000.00")

    def test_int_money_with_floats(self):
        self.assertEqual(repr(Money(float(10.01))), "$10.01")
        self.assertEqual(repr(Money(float(10.01))), "$10.01")

    def test_init_money_with_raw_repr(self):
        self.assertEqual(repr(Money(amount_raw=1001000)), "$10.01")
        if TEST_LONG_VALUES:
            self.assertEqual(
                repr(Money(amount_raw=long(1001000))),  # noqa: F821
                "$10.01")

    def test_init_money_with_currency(self):
        self.assertEqual(repr(Money(10, CURRENCIES['IDR'])), "Rp 10")
        self.assertEqual(repr(Money(10000, CURRENCIES['IDR'])), "Rp 10000")
        self.assertEqual(repr(Money(-1000000, CURRENCIES['IDR'])),
                         "Rp -1000000")

    def test_rounding_dollars(self):
        # US Dollars should use 2 decimal point rounding for amount
        money1 = Money(-10.009)
        self.assertEqual(money1.amount, -10.01)
        self.assertEqual(money1.amount_raw, -1000900)
        self.assertEqual(repr(money1), "-$10.01")

        money2 = Money(10.005)
        self.assertEqual(money2.amount, 10.01)
        self.assertEqual(money2.amount_raw, 1000500)
        self.assertEqual(repr(money2), "$10.01")

        money3 = Money(10.004)
        self.assertEqual(money3.amount, 10.00)
        self.assertEqual(money3.amount_raw, 1000400)
        self.assertEqual(repr(money3), "$10.00")

        money4 = Money(-10.00001)
        self.assertEqual(money4.amount, -10.00)
        self.assertEqual(money4.amount_raw, -1000001)
        self.assertEqual(repr(money4), "-$10.00")

        money5 = Money(amount_raw=7)
        self.assertEqual(money5.amount, 0.0)
        self.assertEqual(money5.amount_raw, 7)
        self.assertEqual(repr(money5), "$0.00")

    def test_rounding_rupiah(self):
        #Rupiah should always round to the nearest integer
        money1 = Money(10, CURRENCIES['IDR'])
        self.assertEqual(money1.amount, 10.0)
        self.assertEqual(money1.amount_raw, 10)
        self.assertEqual(repr(money1), "Rp 10")

        money2 = Money(amount_raw=11, currency=CURRENCIES['IDR'])
        self.assertEqual(money2.amount, 11.0)
        self.assertEqual(money2.amount_raw, 11)
        self.assertEqual(repr(money2), "Rp 11")

    def test_amount_str(self):
        money1 = Money(10000, CURRENCIES['USD'])
        self.assertEqual('10,000.00', money1.amount_str())

        money2 = Money(10000, CURRENCIES['IDR'])
        self.assertEqual('10000', money2.amount_str())

    def test_bad_init_both_amount_args_passed(self):
        with self.assertRaises(ValueError):
            Money(amount=10, amount_raw=10)

        with self.assertRaises(ValueError):
            Money()

    def test_bad_init_bad_currency(self):
        with self.assertRaises(TypeError):
            Money(10, None)

    def test_bad_init_bad_raw_amount(self):
        with self.assertRaises(TypeError):
            Money(amount_raw=10.0)

    def test_bad_init_bad_amount(self):
        with self.assertRaises(TypeError):
            Money('10.00')

class HumanizeCurrencyTestCase(TestCase):
    def test_humanize_currency(self):
        self.assertEqual(str(humanize_credits(12000, CURRENCIES['USD'])),
                "$0.12")
        self.assertEqual(str(humanize_credits(12000, CURRENCIES['IDR'])),
                "Rp 12000")

    def test_parse_credits(self):
        self.assertEqual(1200, parse_credits('1,200').amount)
        self.assertEqual(1200.15, parse_credits('1,200.15').amount)
        self.assertEqual(-123456789.15,
                parse_credits('-123,456,789.15').amount)

    def test_parse_credits_bad(self):
        with self.assertRaises(ValueError):
            parse_credits('12,00')

        with self.assertRaises(ValueError):
            parse_credits('12.000,21')
