"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from osmocom.vty.subscribers import Subscribers
from osmocom.vty.network import Network
from osmocom.vty.bts import BTS
from osmocom.vty.trx import TRX

import json

# IP of VTTY to test on
HOST = '127.0.0.1'

if __name__ == "__main__":
    with TRX(host=HOST) as t:
        t.set_arfcn(0,0,0)
        print(t.running_config(0,0))
        data = t.show(0, 0)
        assert data['arfcn'] == '0'
        assert data['id'] == '0'
        assert data['bts_id'] == '0'
        assert data['description'] == '(null)'
        assert len(data['nominal_power']) > 0
        assert data['attenuation'] == '0'
        assert len(data['power']) > 0
    with Network(host=HOST) as n:
        n.set_mcc(901)
        n.set_mnc(55)
        n.set_short_name('Test')
        n.set_long_name('Test_Network')
        data = n.show()
        print(data)
        assert len(data) == 13, len(data)
        assert data['mcc'] == '901', 'Failed to set mcc'
        assert data['mnc'] == '55', 'Failed to set mnc'
        assert data['short_name'] == 'Test', 'Failed to set shortname'
        assert data['long_name'] == 'Test_Network', 'Failed to set longname'
        print(n.running_config())
    with BTS(host=HOST) as b:
        b.set_type(0, 'sysmobts')
        b.set_cell_identity(0, 1)
        b.set_location_area_code(0, 3)
        b.set_bsic(0, 61)
        b.set_band(0, 'DCS1800')
        data = b.show(0)
        print(data)
        assert len(data) > 14, len(data)
        assert data['ms_max_power'] != None
        assert data['ci'] == '1'
        assert data['ms_min_rx'] == '-110'
        assert data['bsic'] == '61'
        assert data['bcc'] == '5'
        assert data['trx_count'] == '1'
        assert data['lac'] == '3'
        assert data['band'] == 'DCS1800'
        assert data['hysteresis'] == '4'
        assert data['rach_max_transmissions'] == '7'
        assert data['rach_tx_int'] == '9'
        assert data['ncc'] == '7'
        assert data['type'] == 'sysmobts'
        assert data['id'] == '0'
        assert data['description'] == '(null)'
        print(b.running_config(0))
    with Subscribers(host=HOST) as o:
        o.create('901550000000001')
        o.set_extension('901550000000001', '5722543')
        o.set_name('901550000000001', 'Omar')
        o.set_authorized('901550000000001', 1)
        data = o.show('imsi', '901550000000001')
        print(data)
        assert len(data) == 11, len(data)
        assert data['name'] == 'Omar'
        assert data['extension'] == '5722543'
        assert data['authorized'] == '1'
        assert data['lac'] == '0'
        assert data['use_count'] == '1'
        assert data['paging'] == 'not'
        assert data['expiration'] == 'Thu, 01 Jan 1970 00:00:00 +0000'
        assert data['requests'] == '0'
        assert data['imsi'] == '901550000000001'
        assert data['lac_hex'] == '0'
        raised_exception = False
        try:
          o.set_authorized('901550000000111', 1)
        except ValueError:
          raised_exception = True
        assert raised_exception == True
        o.delete('901550000000001')
        raised_exception = False
        try:
          o.delete('901550000000001')
        except ValueError:
          raised_exception = True
        assert raised_exception == True
