"""Tests for the subscriber helper methods at core.subscriber.

Run this test from the project root:
    $ nosetests core.tests.subscriber_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import json
from random import randrange
import unittest

from core.subscriber import subscriber


class CreditTest(unittest.TestCase):
    """Testing credit changes.

    The openbts-python package handles credit querying and updates, but the
    subscriber module add some small utilities for credit addition and
    subtraction.
    """

    TEST_IMSI = 'IMSI901550000000084'
    TEST_MSISDN = '12155551212'

    @classmethod
    def setUpClass(cls):
        subscriber.create_subscriber(cls.TEST_IMSI, cls.TEST_MSISDN)

    def test_credit_delta_type_enforcement(self):
        """The convention is to pass credit changes as a string.

        It should be possible to convert the string to an int and the value
        should be greater than zero in all cases, even when subtracting credit.
        """
        # Each of these values should cause a TypeError.
        invalid_values = ['one thousand', '93f']
        for value in invalid_values:
            with self.assertRaises(ValueError):
                subscriber.add_credit(self.TEST_IMSI, value)
            with self.assertRaises(ValueError):
                subscriber.subtract_credit(self.TEST_IMSI, value)
        # These increments should be allowed.
        valid_values = ['0', '2', '1000', 1000, 0.1, 999.9, -1000.4]
        for value in valid_values:
            subscriber.add_credit(self.TEST_IMSI, value)
            subscriber.subtract_credit(self.TEST_IMSI, value)

    def test_add_credit(self):
        """ We can add credit to a subscriber's balance. """
        increment = randrange(1, 1000)
        prior = subscriber.get_account_balance(self.TEST_IMSI)
        subscriber.add_credit(self.TEST_IMSI, increment)
        after = subscriber.get_account_balance(self.TEST_IMSI)
        self.assertEqual(prior + increment, after)

    def test_subtract_credit(self):
        """ We can subtract credit from a subscriber's balance. """
        prior = randrange(1, 1000)  # add some credit first
        subscriber.add_credit(self.TEST_IMSI, prior)
        decrement = randrange(0, prior)
        subscriber.subtract_credit(self.TEST_IMSI, decrement)
        after = subscriber.get_account_balance(self.TEST_IMSI)
        self.assertEqual(prior - int(decrement), after)

    def test_add_existing_sub(self):
        """ Adding an existing IMSI should raise ValueError. """
        with self.assertRaises(ValueError):
            subscriber.create_subscriber(self.TEST_IMSI, self.TEST_MSISDN)

    def test_get_all_subscribers(self):
        """ We can get a list of all registered subscribers. """
        imsi0 = 'IMSI90155%010d' % (randrange(100, 1e10))
        imsi1 = 'IMSI90156%010d' % (randrange(100, 1e10))
        imsi2 = 'IMSI90157%010d' % (randrange(100, 1e10))
        subscriber.create_subscriber(imsi0, '')  # MSISDN unused
        subscriber.create_subscriber(imsi1, '')  # MSISDN unused
        subscriber.create_subscriber(imsi2, '')  # MSISDN unused
        subs = subscriber.get_subscriber_states()
        expected = {
            imsi0: '',  # we don't get the MSISDN back
            imsi1: '',
            imsi2: '',
            self.TEST_IMSI: '',
        }
        self.assertEqual(len(expected), len(subs))
        for imsi in list(subs.keys()):
            self.assertTrue(imsi in expected)

    def test_get_one_subscriber(self):
        """ We can get a list of specific subscribers. """
        imsi0 = 'IMSI90155%010d' % (randrange(100, 1e10))
        imsi1 = 'IMSI90156%010d' % (randrange(100, 1e10))
        imsi2 = 'IMSI90157%010d' % (randrange(100, 1e10))
        subscriber.create_subscriber(imsi0, '')  # MSISDN unused
        subscriber.create_subscriber(imsi1, '')  # MSISDN unused
        subscriber.create_subscriber(imsi2, '')  # MSISDN unused
        subs = subscriber.get_subscriber_states([imsi0, imsi1])
        self.assertEqual(len(subs), 2)
        self.assertTrue(imsi0 in subs)
        self.assertTrue(imsi1 in subs)

    def test_negative_balance(self):
        """Sub balances are clamped at a min of zero.

        If they go lower, we have made a mistake in the billing system as the
        procedure is to first check if a sub has the funds to complete an
        operation and then, if so, to complete the operation and bill for it.
        When we previously allowed negative sub balances it created some
        confusing displays in the dashboard.
        """
        prior = subscriber.get_account_balance(self.TEST_IMSI)
        decrement = prior + randrange(1, 1000)
        subscriber.subtract_credit(self.TEST_IMSI, decrement)
        self.assertEqual(0, subscriber.get_account_balance(self.TEST_IMSI))
