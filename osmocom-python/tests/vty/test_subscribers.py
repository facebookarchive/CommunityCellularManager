"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import osmocom.vty.subscribers

from .base import MockSocketTestCase
from . import get_fixture_path

class SubscriberCreateTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_create.txt')

    def test_create(self):
        """Test create subscriber."""
        with osmocom.vty.subscribers.Subscribers() as s:
            data = s.create('901550000000001')
            self.assertEqual(data['name'], 'Omar')
            self.assertEqual(data['extension'], '5722543')
            self.assertEqual(data['authorized'], '1')
            self.assertEqual(data['lac'], '0')
            self.assertEqual(data['use_count'], '1')
            self.assertEqual(data['paging'], 'not')
            self.assertEqual(data['expiration'], 'Wed, 31 Dec 1969 16:00:00 -0800')
            self.assertEqual(data['requests'], '0')
            self.assertEqual(data['id'], '2')
            self.assertEqual(data['imsi'], '901550000000001')
            self.assertEqual(data['lac_hex'], '0')


class SubscriberSetTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_set.txt')

    @classmethod
    def setUpClass(cls):
        super(SubscriberSetTestCase, cls).setUpClass()
        cls.s = osmocom.vty.subscribers.Subscribers()
        cls.s.open()

    @classmethod
    def tearDownClass(cls):
        super(SubscriberSetTestCase, cls).tearDownClass()
        cls.s.close()

    def test_set_extension(self):
        """Test set subscriber extension."""
        self.s.set_extension('IMSI901550000000001', '5722543')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
        'subscriber imsi 901550000000001 extension 5722543\r\n' +
        'disable\r\n')

    def test_set_name(self):
        """Test set subscriber name."""
        self.s.set_name('901550000000001', 'Omar')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
        'subscriber imsi 901550000000001 name Omar\r\n' +
        'disable\r\n')

    def test_set_authorized(self):
        """Test set subscriber auth."""
        self.s.set_authorized('901550000000001', 1)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
        'subscriber imsi 901550000000001 authorized 1\r\n' +
        'disable\r\n')


class SubscriberSetErrorTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_set_error.txt')

    @classmethod
    def setUpClass(cls):
        super(SubscriberSetErrorTestCase, cls).setUpClass()
        cls.s = osmocom.vty.subscribers.Subscribers()
        cls.s.open()

    @classmethod
    def tearDownClass(cls):
        super(SubscriberSetErrorTestCase, cls).tearDownClass()
        cls.s.close()

    def test_set_not_exists(self):
        """Ensure that setting a non-existent user results in error"""
        with self.assertRaises(ValueError):
            self.s.set_authorized('901550000000111', 1)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
        'subscriber imsi 901550000000111 authorized 1\r\n' +
        'disable\r\n')


class SubscriberGetTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_get.txt')

    @classmethod
    def setUpClass(cls):
        super(SubscriberGetTestCase, cls).setUpClass()
        cls.s = osmocom.vty.subscribers.Subscribers()
        cls.s.open()

    def test_get(self):
        """Test getting a subscriber."""
        data = self.s.show('imsi', 'IMSI901550000000001')
        self.assertEqual(data['name'], 'Omar')
        self.assertEqual(data['extension'], '5722543')
        self.assertEqual(data['authorized'], '1')
        self.assertEqual(data['lac'], '0')
        self.assertEqual(data['use_count'], '1')
        self.assertEqual(data['paging'], 'not')
        self.assertEqual(data['expiration'], 'Wed, 31 Dec 1969 16:00:00 -0800')
        self.assertEqual(data['requests'], '0')
        self.assertEqual(data['id'], '2')
        self.assertEqual(data['imsi'], '901550000000001')
        self.assertEqual(data['lac_hex'], '0')


class SubscriberTestIMSITestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_get_test_imsi.txt')

    @classmethod
    def setUpClass(cls):
        super(SubscriberTestIMSITestCase, cls).setUpClass()
        cls.s = osmocom.vty.subscribers.Subscribers()
        cls.s.open()

    def test_pad_imsi_len_15(self):
        """Test getting a subscriber with a zero prefixed imsi."""
        data = self.s.show('imsi', 'IMSI001501252002526')
        # The IMSI is length 15 with zero-padding
        self.assertEqual(len(data['imsi']), 15)
        self.assertEqual(data['imsi'], '001501252002526')


class SubscriberGetInvalidTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_get_error.txt')

    def test_get_error(self):
        """Getting a subscriber that doesnt exist will raise a ValueError"""
        with osmocom.vty.subscribers.Subscribers() as s:
            with self.assertRaises(ValueError):
                s.show('imsi', '901550000000002')


class SubscriberDeleteTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_delete.txt')

    @classmethod
    def setUpClass(cls):
        super(SubscriberDeleteTestCase, cls).setUpClass()
        cls.s = osmocom.vty.subscribers.Subscribers()
        cls.s.open()

    @classmethod
    def tearDownClass(cls):
        super(SubscriberDeleteTestCase, cls).tearDownClass()
        cls.s.close()

    def test_create(self):
        """Test that we send the correct command on creation"""
        self.s.create('901550000000001')
        self.assertEqual(self.sendall_buffer, 'subscriber create imsi 901550000000001\r\n')

    def test_delete(self):
        """Test deleting the subscriber we just created."""
        self.s.delete('901550000000001')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
        'subscriber imsi 901550000000001 delete\r\n' +
        'disable\r\n')


class SubscriberDeleteErrorTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('subscriber_delete_error.txt')

    @classmethod
    def setUpClass(cls):
        super(SubscriberDeleteErrorTestCase, cls).setUpClass()
        cls.s = osmocom.vty.subscribers.Subscribers()
        cls.s.open()

    @classmethod
    def tearDownClass(cls):
        super(SubscriberDeleteErrorTestCase, cls).tearDownClass()
        cls.s.close()

    def test_delete_not_exist(self):
        """Deleting a subscriber that doesn't exist causes an error."""
        with self.assertRaises(ValueError):
            self.s.delete('901550000000001')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
        'subscriber imsi 901550000000001 delete\r\n' +
        'disable\r\n')
