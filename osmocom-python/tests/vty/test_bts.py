"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import osmocom.vty.bts

from .base import MockSocketTestCase
from . import get_fixture_path

class BTSSetTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('bts_set.txt')

    @classmethod
    def setUpClass(cls):
        super(BTSSetTestCase, cls).setUpClass()
        cls.b = osmocom.vty.bts.BTS()
        cls.b.open()

    @classmethod
    def tearDownClass(cls):
        super(BTSSetTestCase, cls).tearDownClass()
        cls.b.close()

    def test_set_type(self):
        """Test writing bts settings."""
        self.b.set_type(0, 'sysmobts')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'bts 0\r\n' +
            'type sysmobts\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

    def test_set_cell_idenity(self):
        self.b.set_cell_identity(0, 1)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'bts 0\r\n' +
            'cell_identity 1\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

    def test_set_location_area_code(self):
        self.b.set_location_area_code(0, 3)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'bts 0\r\n' +
            'location_area_code 3\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

    def test_set_bsic(self):
        self.b.set_bsic(0, 61)
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'bts 0\r\n' +
            'base_station_id_code 61\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')

    def test_set_band(self):
        self.b.set_band(0, 'DCS1800')
        self.assertEqual(self.sendall_buffer, 'enable\r\n' +
            'configure terminal\r\n' +
            'network\r\n' +
            'bts 0\r\n' +
            'band DCS1800\r\n' +
            'write\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'exit\r\n' +
            'disable\r\n')


class BTSGetOnlineTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('bts_get_online.txt')

    @classmethod
    def setUpClass(cls):
        super(BTSGetOnlineTestCase, cls).setUpClass()
        cls.b = osmocom.vty.bts.BTS()
        cls.b.open()

    def test_get_online(self):
        """Test reading bts status for online bts."""
        data = self.b.show(0)
        self.assertEqual(data['oml_link'], 'connected')
        self.assertEqual(data['ccch_sdcch4_load'], '0')
        self.assertEqual(data['ccch_sdcch4_max'], '4')
        self.assertEqual(data['tch_f_load'], '0')
        self.assertEqual(data['tch_f_max'], '2')
        self.assertEqual(data['tch_h_load'], '0')
        self.assertEqual(data['tch_h_max'], '2')
        self.assertEqual(data['sdcch8_load'], '0')
        self.assertEqual(data['sdcch8_max'], '8')
        self.assertEqual(data['tch_f_pdch_load'], '0')


class BTSGetOfflineTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('bts_get_offline.txt')

    @classmethod
    def setUpClass(cls):
        super(BTSGetOfflineTestCase, cls).setUpClass()
        cls.b = osmocom.vty.bts.BTS()
        cls.b.open()

    def test_get_offline(self):
        """Test reading bts settings."""
        data = self.b.show(0)
        self.assertEqual(data['ms_max_power'], '12')
        self.assertEqual(data['ci'], '1')
        self.assertEqual(data['ms_min_rx'], '-110')
        self.assertEqual(data['bsic'], '61')
        self.assertEqual(data['bcc'], '5')
        self.assertEqual(data['trx_count'], '1')
        self.assertEqual(data['lac'], '3')
        self.assertEqual(data['band'], 'DCS1800')
        self.assertEqual(data['hysteresis'], '4')
        self.assertEqual(data['rach_max_transmissions'], '7')
        self.assertEqual(data['rach_tx_int'], '9')
        self.assertEqual(data['ncc'], '7')
        self.assertEqual(data['type'], 'sysmobts')
        self.assertEqual(data['id'], '0')
        self.assertEqual(data['description'], '(null)')
        self.assertEqual(data['oml_link'], 'disconnected')


class BTSConnectedOnlineTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('bts_get_online.txt')

    @classmethod
    def setUpClass(cls):
        super(BTSConnectedOnlineTestCase, cls).setUpClass()
        cls.b = osmocom.vty.bts.BTS()
        cls.b.open()

    def test_get_online(self):
        """This should return the bts is connected."""
        self.assertEqual(self.b.is_connected(0), True)


class BTSConnectedOfflineTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('bts_get_offline.txt')

    @classmethod
    def setUpClass(cls):
        super(BTSConnectedOfflineTestCase, cls).setUpClass()
        cls.b = osmocom.vty.bts.BTS()
        cls.b.open()

    def test_get_offline(self):
        """This should return the bts is not connected."""
        self.assertEqual(self.b.is_connected(0), False)


class BTSLoadOnlineTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('bts_get_online.txt')

    @classmethod
    def setUpClass(cls):
        super(BTSLoadOnlineTestCase, cls).setUpClass()
        cls.b = osmocom.vty.bts.BTS()
        cls.b.open()

    def test_get_online_load(self):
        """Read the loads for an online BTS without load."""
        load = self.b.get_load(0)
        self.assertEqual(load['ccch_sdcch4_load'], 0)
        self.assertEqual(load['ccch_sdcch4_max'], 4)
        self.assertEqual(load['tch_f_load'], 0)
        self.assertEqual(load['tch_f_max'], 2)
        self.assertEqual(load['tch_h_load'], 0)
        self.assertEqual(load['tch_h_max'], 2)
        self.assertEqual(load['sdcch8_load'], 0)
        self.assertEqual(load['sdcch8_max'], 8)
        self.assertEqual(load['tch_f_pdch_load'], 0)
        self.assertEqual(load['tch_f_pdch_max'], 1)


class BTSLoadOfflineTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('bts_get_offline.txt')

    @classmethod
    def setUpClass(cls):
        super(BTSLoadOfflineTestCase, cls).setUpClass()
        cls.b = osmocom.vty.bts.BTS()
        cls.b.open()

    def test_get_offline_load(self):
        """This load readings should be zero for an offline BTS."""
        load = self.b.get_load(0)
        self.assertEqual(load['ccch_sdcch4_max'], 0)
        self.assertEqual(load['ccch_sdcch4_load'], 0)
        self.assertEqual(load['tch_f_load'], 0)
        self.assertEqual(load['tch_f_max'], 0)
        self.assertEqual(load['tch_h_load'], 0)
        self.assertEqual(load['tch_h_max'], 0)
        self.assertEqual(load['sdcch8_load'], 0)
        self.assertEqual(load['sdcch8_max'], 0)
        self.assertEqual(load['tch_f_pdch_load'], 0)
        self.assertEqual(load['tch_f_pdch_max'], 0)


class BTSRunningConfigTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('running_config.txt')

    def test_running_config(self):
        """Test reading bts settings."""
        with osmocom.vty.bts.BTS() as b:
            data = b.running_config(0)
            self.assertEqual(data['type'], 'sysmobts')
            self.assertEqual(data['channel-descrption bs-ag-blks-res'], '1')
            self.assertEqual(data['force-combined-si'], 'no')
            self.assertEqual(data['trx']['0']['rf_locked'], '0')
            self.assertEqual(data['trx']['0']['rsl e1 tei']['0']['timeslot']['0']['phys_chan_config'], 'CCCH+SDCCH4')
            self.assertEqual(data['trx']['0']['rsl e1 tei']['0']['timeslot']['1']['phys_chan_config'], 'TCH/F')
            self.assertEqual(data['trx']['0']['rsl e1 tei']['0']['timeslot']['7']['phys_chan_config'], 'PDCH')
