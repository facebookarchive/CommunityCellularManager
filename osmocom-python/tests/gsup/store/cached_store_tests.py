"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

from osmocom.gsup.store.util import SIDUtils
from osmocom.gsup.store.base import DuplicateSubscriberError
from osmocom.gsup.store.base import SubscriberNotFoundError
from osmocom.gsup.store.cached_store import CachedStore
from osmocom.gsup.store.sqlite import SqliteStore
from osmocom.gsup.store.protos.subscriber_pb2 import (GSMSubscription,
                                                      SubscriberData)


class StoreTests(unittest.TestCase):
    """
    Test class for the CachedStore subscriber storage
    """

    def setUp(self):
        cache_size = 3
        sqlite = SqliteStore("file::memory:")
        self._store = CachedStore(sqlite, cache_size)

    def _add_subscriber(self, sid):
        sub = SubscriberData(sid=SIDUtils.to_pb(sid))
        self._store.add_subscriber(sub)
        return (sid, sub)

    def test_subscriber_addition(self):
        """
        Test if subscriber addition works as expected
        """
        self.assertEqual(self._store.list_subscribers(), [])
        (sid1, sub1) = self._add_subscriber('IMSI11111')
        self.assertEqual(self._store.list_subscribers(), [sid1])
        (sid2, sub2) = self._add_subscriber('IMSI22222')
        self.assertEqual(self._store.list_subscribers(), [sid1, sid2])

        # Check if adding an existing user throws an exception
        with self.assertRaises(DuplicateSubscriberError):
            self._store.add_subscriber(sub2)
        self.assertEqual(self._store.list_subscribers(), [sid1, sid2])

        self.assertEqual(self._store._cache_list(), [sid1, sid2])

        self._store.delete_all_subscribers()
        self.assertEqual(self._store.list_subscribers(), [])
        self.assertEqual(self._store._cache_list(), [])

    def test_subscriber_deletion(self):
        """
        Test if subscriber deletion works as expected
        """
        (sid1, sub1) = self._add_subscriber('IMSI11111')
        (sid2, sub2) = self._add_subscriber('IMSI22222')
        self.assertEqual(self._store.list_subscribers(), [sid1, sid2])
        self.assertEqual(self._store._cache_list(), [sid1, sid2])

        self._store.delete_subscriber(sid2)
        self.assertEqual(self._store.list_subscribers(), [sid1])
        self.assertEqual(self._store._cache_list(), [sid1])

        # Deleting a non-existent user would be ignored
        self._store.delete_subscriber(sid2)
        self.assertEqual(self._store.list_subscribers(), [sid1])
        self.assertEqual(self._store._cache_list(), [sid1])

        self._store.delete_subscriber(sid1)
        self.assertEqual(self._store.list_subscribers(), [])
        self.assertEqual(self._store._cache_list(), [])

    def test_subscriber_retrieval(self):
        """
        Test if subscriber retrieval works as expected
        """
        (sid1, sub1) = self._add_subscriber('IMSI11111')
        self.assertEqual(self._store.list_subscribers(), [sid1])
        self.assertEqual(self._store._cache_list(), [sid1])
        self.assertEqual(self._store.get_subscriber_data(sid1), sub1)

        with self.assertRaises(SubscriberNotFoundError):
            self._store.get_subscriber_data('IMSI30000')
        self.assertEqual(self._store._cache_list(), [sid1])

        self._store.delete_all_subscribers()
        self.assertEqual(self._store.list_subscribers(), [])
        self.assertEqual(self._store._cache_list(), [])

    def test_subscriber_edit(self):
        """
        Test if subscriber edit works as expected
        """
        (sid1, sub1) = self._add_subscriber('IMSI11111')
        self.assertEqual(self._store.get_subscriber_data(sid1), sub1)
        self.assertEqual(self._store._cache_list(), [sid1])

        # Update from cache
        with self._store.edit_subscriber(sid1) as subs:
            subs.gsm.state = GSMSubscription.ACTIVE
        self.assertEqual(self._store.get_subscriber_data(sid1).gsm.state,
                         GSMSubscription.ACTIVE)
        self.assertEqual(self._store._cache_list(), [sid1])

        # Update from persistent store after eviction
        (sid2, sub2) = self._add_subscriber('IMSI22222')
        (sid3, sub3) = self._add_subscriber('IMSI33333')
        (sid4, sub4) = self._add_subscriber('IMSI44444')
        self.assertEqual(self._store._cache_list(), [sid2, sid3, sid4])
        with self._store.edit_subscriber(sid1) as subs:
            subs.gsm.state = GSMSubscription.ACTIVE
        self.assertEqual(self._store.get_subscriber_data(sid1).gsm.state,
                         GSMSubscription.ACTIVE)
        self.assertEqual(self._store._cache_list(), [sid3, sid4, sid1])

        with self.assertRaises(SubscriberNotFoundError):
            with self._store.edit_subscriber('IMSI3000') as subs:
                pass

    def test_lru_cache_invl(self):
        """
        Test if LRU eviction works as expected
        """
        (sid1, sub1) = self._add_subscriber('IMSI11111')
        (sid2, sub2) = self._add_subscriber('IMSI22222')
        (sid3, sub3) = self._add_subscriber('IMSI33333')
        (sid4, sub4) = self._add_subscriber('IMSI44444')
        (sid5, sub5) = self._add_subscriber('IMSI55555')
        (sid6, sub6) = self._add_subscriber('IMSI66666')

        self._store.get_subscriber_data(sid1)
        self.assertEqual(self._store._cache_list(), [sid5, sid6, sid1])
        self._store.get_subscriber_data(sid2)
        self.assertEqual(self._store._cache_list(), [sid6, sid1, sid2])
        self._store.get_subscriber_data(sid3)
        self.assertEqual(self._store._cache_list(), [sid1, sid2, sid3])

        self._store.get_subscriber_data(sid2)
        self.assertEqual(self._store._cache_list(), [sid1, sid3, sid2])

        self._store.get_subscriber_data(sid4)
        self.assertEqual(self._store._cache_list(), [sid3, sid2, sid4])

        self._store.get_subscriber_data(sid5)
        self.assertEqual(self._store._cache_list(), [sid2, sid4, sid5])

        self._store.get_subscriber_data(sid6)
        self.assertEqual(self._store._cache_list(), [sid4, sid5, sid6])

        self._store.delete_all_subscribers()
        self.assertEqual(self._store.list_subscribers(), [])
        self.assertEqual(self._store._cache_list(), [])
