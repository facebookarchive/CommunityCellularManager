"""Tests for models.Number.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from unittest import TestCase

from endagaweb import models


class DeletionTest(TestCase):
    """We can delete Subs but have Numbers stick around."""

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
        self.number = models.Number(
            number='5551234', state="inuse", network=self.bts.network,
            kind="number.nexmo.monthly", subscriber=self.subscriber)
        self.number.save()

    def tearDown(self):
        """Make sure everything is cleaned up."""
        self.user.delete()
        self.user_profile.delete()
        self.user_profile.network.delete()
        self.bts.delete()
        if models.Subscriber.objects.filter(pk=self.subscriber.pk):
            self.subscriber.delete()
        self.number.delete()

    def test_delete_sub(self):
        """We can delete Subs and Numbers should live on."""
        self.assertEqual(1, models.Number.objects.filter(
            pk=self.number.pk).count())
        self.assertEqual(self.subscriber, self.number.subscriber)
        self.subscriber.delete()
        self.assertEqual(1, models.Number.objects.filter(
            pk=self.number.pk).count())
        # Reload the Number from the DB.
        self.number = models.Number.objects.get(pk=self.number.pk)
        self.assertEqual(None, self.number.subscriber)
