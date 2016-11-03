"""Tests for models.UsageEvent.

Note that bts_tests also have quite a few tests related to UsageEvents.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
from unittest import TestCase

import pytz

from endagaweb import models


class BaseTestCase(TestCase):
    """A test case from which others inherit."""

    @classmethod
    def setUpClass(cls):
        """Using setUpClass so we don't create duplicate objects."""
        cls.user = models.User(username="mmm", email="m@e.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.bts = models.BTS(uuid="333222", nickname="test-bts-name!",
                             inbound_url="http://localhost/333222/test",
                             network=cls.user_profile.network)
        cls.bts.save()
        cls.subscriber = models.Subscriber.objects.create(
            balance=10000, name='test-sub-name', imsi='IMSI00123',
            network=cls.bts.network)
        cls.subscriber.save()

    @classmethod
    def tearDownClass(cls):
        """Delete some of the things we created."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.subscriber.delete()


class UsageEventSubscriberOpsTest(BaseTestCase):
    """We can capture subscriber creation and deletion in usage events."""

    def test_generate_add_imsi_event(self):
        """We can generate and save an add_imsi event."""
        now = datetime.datetime.now(pytz.utc)
        event = models.UsageEvent.objects.create(
            subscriber=self.subscriber, date=now, kind='add_imsi',
            bts=self.bts, subscriber_imsi=self.subscriber.imsi,
            bts_uuid=self.bts.uuid,
            reason='added %s' % self.subscriber.imsi)
        event.save()
        self.assertEqual(now, event.date)

    def test_generate_delete_imsi_event(self):
        """We can generate and save a delete_imsi event."""
        now = datetime.datetime.now(pytz.utc)
        event = models.UsageEvent.objects.create(
            subscriber=self.subscriber, date=now, kind='delete_imsi',
            bts=self.bts, subscriber_imsi=self.subscriber.imsi,
            bts_uuid=self.bts.uuid,
            reason='deactivated %s' % self.subscriber.imsi)
        event.save()
        self.assertEqual(now, event.date)


class UsageEventNumberOpsTest(BaseTestCase):
    """We can capture number creation and deletion in usage events."""

    def test_generate_add_number_event(self):
        """We can create and save an add_number event."""
        now = datetime.datetime.now(pytz.utc)
        event = models.UsageEvent.objects.create(
            subscriber=self.subscriber, date=now, kind='add_number',
            bts=self.bts, reason='created 19195551234',
            to_number='19195551234')
        event.save()
        self.assertEqual(now, event.date)

    def test_generate_deactivate_number_event(self):
        """We can create and save a deactivate_number event."""
        now = datetime.datetime.now(pytz.utc)
        event = models.UsageEvent.objects.create(
            subscriber=self.subscriber, date=now, kind='deactivate_number',
            bts=self.bts, reason='deactivated 19195551234',
            to_number='19195551234')
        event.save()
        self.assertEqual(now, event.date)


class DeletionTest(TestCase):
    """We can delete subs but have UEs stick around."""

    def setUp(self):
        self.user = models.User(username="qqq", email="q@e.com")
        self.user.save()
        self.user_profile = models.UserProfile.objects.get(user=self.user)
        self.bts = models.BTS(uuid="133222", nickname="test-bts-name!",
                              inbound_url="http://localhost/133222/test",
                              network=self.user_profile.network)
        self.bts.save()
        self.subscriber = models.Subscriber.objects.create(
            balance=10000, name='test-sub-name', imsi='IMSI00123',
            network=self.bts.network)
        self.subscriber.save()
        now = datetime.datetime.now(pytz.utc)
        self.event = models.UsageEvent(
            subscriber=self.subscriber, bts=self.bts, date=now,
            kind='local_call', reason='test', oldamt=500, newamt=400,
            change=100, call_duration=600)
        self.event.save()

    def tearDown(self):
        """Make sure everything is cleaned up."""
        self.user.delete()
        self.user_profile.delete()
        self.user_profile.network.delete()
        self.bts.delete()
        if models.Subscriber.objects.filter(pk=self.subscriber.pk):
            self.subscriber.delete()
        self.event.delete()

    def test_delete_sub(self):
        """We can delete subs and UEs should live on."""
        self.assertEqual(1, models.UsageEvent.objects.filter(
            pk=self.event.pk).count())
        self.assertEqual(self.subscriber, self.event.subscriber)
        self.subscriber.delete()
        self.assertEqual(1, models.UsageEvent.objects.filter(
            pk=self.event.pk).count())
        # Reload the event from the DB.
        self.event = models.UsageEvent.objects.get(pk=self.event.pk)
        self.assertEqual(None, self.event.subscriber)
