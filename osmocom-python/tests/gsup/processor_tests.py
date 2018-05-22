"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

from unittest.mock import Mock

from osmocom.gsup.crypto.utils import CryptoError
from osmocom.gsup import processor
from osmocom.gsup.store.base import SubscriberNotFoundError
from osmocom.gsup.store.sqlite import SqliteStore
from osmocom.gsup.store.util import SIDUtils
from osmocom.gsup.store.protos.subscriber_pb2 import (GSMSubscription,
                                     SubscriberData, SubscriberState)


def _dummy_auth_tuple():
    rand = b'ni\x89\xbel\xeeqTT7p\xae\x80\xb1\xef\r'
    sres = b'\xd4\xac\x8bS'
    key = b'\x9f\xf54.\xb9]\x88\x00'
    return (rand, sres, key)

class ProcessorTests(unittest.TestCase):
    """
    Tests for the Processor
    """

    def setUp(self):
        store = SqliteStore('file::memory:')

        self._processor = processor.Processor(store)

        # Add some test users
        (rand, sres, gsm_key) = _dummy_auth_tuple()
        gsm = GSMSubscription(state=GSMSubscription.ACTIVE,
                              auth_tuples=[rand + sres + gsm_key])

        state = SubscriberState()
        sub1 = SubscriberData(sid=SIDUtils.to_pb('IMSI11111'), gsm=gsm,
                              state=state)
        sub2 = SubscriberData(sid=SIDUtils.to_pb('IMSI22222'), # No auth keys
                              gsm=GSMSubscription(state=GSMSubscription.ACTIVE))
        sub3 = SubscriberData(sid=SIDUtils.to_pb('IMSI33333')) # No subscribtion
        store.add_subscriber(sub1)
        store.add_subscriber(sub2)
        store.add_subscriber(sub3)

    def test_gsm_auth_success(self):
        """
        Test if we get the correct auth tuple on success
        """
        self.assertEqual(self._processor.get_gsm_auth_vector('11111'),
                         _dummy_auth_tuple())

    def test_gsm_auth_imsi_unknown(self):
        """
        Test if we get SubscriberNotFoundError exception
        """
        with self.assertRaises(SubscriberNotFoundError):
            self._processor.get_gsm_auth_vector('12345')

    def test_gsm_auth_key_missing(self):
        """
        Test if we get CryptoError if auth key is missing
        """
        with self.assertRaises(CryptoError):
            self._processor.get_gsm_auth_vector('22222')

    def test_gsm_auth_no_subscription(self):
        """
        Test if we get CryptoError if there is no GSM subscription
        """
        with self.assertRaises(CryptoError):
            self._processor.get_gsm_auth_vector('33333')

if __name__ == "__main__":
    unittest.main()
