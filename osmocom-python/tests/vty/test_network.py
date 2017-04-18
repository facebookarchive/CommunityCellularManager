"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import osmocom.vty.network

from .base import MockSocketTestCase
from . import get_fixture_path

class NetworkSetTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('network_set.txt')

    @classmethod
    def setUpClass(cls):
        super(NetworkSetTestCase, cls).setUpClass()
        cls.n = osmocom.vty.network.Network()
        cls.n.open()

    @classmethod
    def tearDownClass(cls):
        super(NetworkSetTestCase, cls).tearDownClass()
        cls.n.close()

    def test_set_mcc(self):
        """Test reading writing network mcc."""
        self.n.set_mcc(901)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'network country code 901\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

    def test_set_mnc(self):
        """Test reading writing network mnc."""
        self.n.set_mnc(55)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'mobile network code 55\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

    def test_set_short_name(self):
        """Test reading writing network short name."""
        self.n.set_short_name('Test')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'short name Test\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

    def test_set_long_name(self):
        """Test reading writing network long name."""
        self.n.set_long_name('Test_Network')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'long name Test_Network\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')


class NetworkSetBadTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('network_set_invalid.txt')

    @classmethod
    def setUpClass(cls):
        super(NetworkSetBadTestCase, cls).setUpClass()
        cls.n = osmocom.vty.network.Network()
        cls.n.open()

    @classmethod
    def tearDownClass(cls):
        super(NetworkSetBadTestCase, cls).tearDownClass()
        cls.n.close()

    def test_set_short_name_space(self):
        """Test writing invalid network short name with space."""
        with self.assertRaises(ValueError):
            self.n.set_short_name('Invalid Space')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'short name Invalid Space\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

class NetworkGetTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('network_get.txt')

    def test_get(self):
        """Test reading writing network settings."""
        with osmocom.vty.network.Network() as n:
            network_data = n.show()
            self.assertEqual(network_data['handover'], 'Off')
            self.assertEqual(network_data['auth_policy'], 'accept-all')
            self.assertEqual(network_data['short_name'], 'Test')
            self.assertEqual(network_data['neci'], '1')
            self.assertEqual(network_data['encryption'], 'A5/0')
            self.assertEqual(network_data['mm_info'], 'On')
            self.assertEqual(network_data['mcc'], '901')
            self.assertEqual(network_data['mnc'], '55')
            self.assertEqual(network_data['long_name'], 'Test_Network')
            self.assertEqual(network_data['rrlp_mode'], 'none')
            self.assertEqual(network_data['lur_reject_cause'], '13')
            self.assertEqual(network_data['bts_count'], '1')
            self.assertEqual(network_data['tch_paging'], '0')
