"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import osmocom.vty.trx

from .base import MockSocketTestCase
from . import get_fixture_path

class TRXSetTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('trx_set.txt')

    @classmethod
    def setUpClass(cls):
        super(TRXSetTestCase, cls).setUpClass()
        cls.t = osmocom.vty.trx.TRX()
        cls.t.open()

    @classmethod
    def tearDownClass(cls):
        super(TRXSetTestCase, cls).tearDownClass()
        cls.t.close()

    def test_set_arfcn(self):
        """Test writing trx settings."""
        self.t.set_arfcn(0,0,1)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'bts 0\r\n' +
            'trx 0\r\n' +
            'arfcn 1\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

class TRXGetTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('trx_get.txt')

    def test_get(self):
        """Test reading trx settings."""
        with osmocom.vty.trx.TRX() as t:
            data = t.show(0,0)
            self.assertEqual(data['arfcn'], '1')
            self.assertEqual(data['id'], '0')
            self.assertEqual(data['bts_id'], '0')
            self.assertEqual(data['description'], '(null)')
            self.assertEqual(data['nominal_power'], '23')
            self.assertEqual(data['attenuation'], '0')
            self.assertEqual(data['power'], '23')
