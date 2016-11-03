"""Tests for models.Subscriber.

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

from datetime import datetime
from random import randrange
import uuid

import pytz

from django.test import TestCase

from ccm.common import crdt
from endagaweb import models


class TestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = models.User(username="km", email="k@m.com")
        user.save()
        user_profile = models.UserProfile.objects.get(user=user)
        cls.network = user_profile.network

    @classmethod
    def add_sub(cls, imsi,
                ev_kind=None, ev_reason=None, ev_date=None,
                balance=0):
        sub = models.Subscriber.objects.create(
            imsi=imsi, network=cls.network, balance=balance)
        if ev_kind:
            if ev_date is None:
                ev_date = datetime.now(pytz.utc)
            ev = models.UsageEvent(
                subscriber=sub, network=cls.network, date=ev_date,
                kind=ev_kind, reason=ev_reason)
            ev.save()
        return sub

    @staticmethod
    def gen_crdt(delta):
        # CRDT updates with the same UUID are merged - the max values of
        # the P and N counters are taken - so we need to ensure the UUID
        # of each update is distinct.
        c = crdt.PNCounter(str(uuid.uuid4()))
        if delta > 0:
            c.increment(delta)
        elif delta < 0:
            c.decrement(-delta)
        return c

    @staticmethod
    def gen_imsi():
        return 'IMSI0%014d' % (randrange(1, 1e10), )

    @staticmethod
    def get_sub(imsi):
        return models.Subscriber.objects.get(imsi=imsi)


class SubscriberBalanceTests(TestBase):
    """
    We can manage subscriber balances.
    """
    def test_sub_get_balance(self):
        """ Test the balance property. """
        bal = randrange(1, 1000)
        sub = self.add_sub(self.gen_imsi(),
                           balance=bal)
        self.assertEqual(sub.balance, bal)

    def test_sub_update_balance(self):
        """ Test that we can add credit to a subscriber. """
        bal = randrange(1, 1000)
        imsi = self.gen_imsi()
        self.add_sub(imsi, balance=bal)
        delta = randrange(1, 1000)
        c = self.gen_crdt(delta)
        models.Subscriber.update_balance(imsi, c)
        self.assertEqual(self.get_sub(imsi).balance, bal + delta)

    def test_sub_update_balance_negative(self):
        """ Test that we can subtract credit from a subscriber. """
        bal = randrange(1, 1000)
        imsi = self.gen_imsi()
        self.add_sub(imsi, balance=bal)
        delta = randrange(0, bal)
        c = self.gen_crdt(-delta)
        models.Subscriber.update_balance(imsi, c)
        self.assertEqual(self.get_sub(imsi).balance, bal - delta)

    def test_sub_change_balance(self):
        """ Test the change_balance class method. """
        bal = randrange(1, 1000)
        sub = self.add_sub(self.gen_imsi(),
                           balance=bal)
        delta = randrange(1, 1000)
        sub.change_balance(delta)
        self.assertEqual(sub.balance, bal + delta)

    def test_sub_balance_setting(self):
        """ Test the balance update fails if balance already set. """
        # works if balance is not yet used
        sub = self.add_sub(self.gen_imsi())
        bal = randrange(1, 1000)
        sub.balance = bal  # works since it's currently zero
        self.assertEqual(sub.balance, bal)
        # throws exception if balance already set
        with self.assertRaises(ValueError):
            sub.balance = randrange(1, 1000)


class ActiveSubscriberTests(TestBase):
    """
    We can identify outbound (in)active Subcribers.
    """
    def test_sub_sans_outbound_activity(self):
        """Use registration data if a sub has no outbound activity."""
        days = 90
        the_past = datetime(year=2014, month=8, day=10, tzinfo=pytz.utc)
        imsi = self.gen_imsi()
        sub = self.add_sub(imsi,
                           'Provisioned',
                           'Provisioned %s' % (imsi, ),
                           ev_date=the_past)
        outbound_inactives = self.network.get_outbound_inactive_subscribers(
            days)
        self.assertItemsEqual([sub], outbound_inactives)

    def test_sub_with_activity(self):
        """Active subs don't appear in inactive list."""
        days = 90
        imsi = self.gen_imsi()
        sub = self.add_sub(imsi,
                           'outside_sms', 'sms sent')
        outbound_inactives = self.network.get_outbound_inactive_subscribers(
            days)
        self.assertFalse(sub in outbound_inactives)
