"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import re

from .base import BaseVTY

class BTS(BaseVTY):

    def __init__(self, host='127.0.0.1', port=4242, timeout=None):
        super(BTS, self).__init__('OpenBSC', host, port, timeout)
        self.PARSE_SHOW = [
            re.compile('BTS (?P<id>\d+) is of (?P<type>[^\s]+) type in band (?P<band>[^\s]+), has CI (?P<ci>\d+) LAC (?P<lac>\d+), BSIC (?P<bsic>\d+) \(NCC=(?P<ncc>\d+), BCC=(?P<bcc>\d+)\) and (?P<trx_count>\d+)'),
            re.compile('Description: (?P<description>[^\s]+)'),
            re.compile('MS Max power: (?P<ms_max_power>-?\d+) dBm'),
            re.compile('Minimum Rx Level for Access: (?P<ms_min_rx>-?\d+) dBm'),
            re.compile('Cell Reselection Hysteresis: (?P<hysteresis>-?\d+) dBm'),
            re.compile('RACH TX-Integer: (?P<rach_tx_int>\d+)'),
            re.compile('RACH Max transmissions: (?P<rach_max_transmissions>\d+)'),
            re.compile('OML Link state: (?P<oml_link>[^\s]+)\.'),
            re.compile('CCCH\+SDCCH4:.+\((?P<ccch_sdcch4_load>\d+)\/(?P<ccch_sdcch4_max>\d+)\)'),
            re.compile('TCH\/F:.+\((?P<tch_f_load>\d+)\/(?P<tch_f_max>\d+)\)'),
            re.compile('TCH\/H:.+\((?P<tch_h_load>\d+)\/(?P<tch_h_max>\d+)\)'),
            re.compile('SDCCH8:.+\((?P<sdcch8_load>\d+)\/(?P<sdcch8_max>\d+)\)'),
            re.compile('TCH\/F_PDCH:.+\((?P<tch_f_pdch_load>\d+)\/(?P<tch_f_pdch_max>\d+)\)')]

    def is_connected(self, bts_id):
        """Returns whether a BTS is connected"""
        status = self.show(bts_id)
        return status['oml_link'] == 'connected'

    def get_load(self, bts_id):
        """Returns a dictionary of channel load"""
        status = self.show(bts_id)
        return {
            'ccch_sdcch4_load': int(status.get('ccch_sdcch4_load', 0)),
            'ccch_sdcch4_max': int(status.get('ccch_sdcch4_max', 0)),
            'tch_f_load': int(status.get('tch_f_load', 0)),
            'tch_f_max': int(status.get('tch_f_max', 0)),
            'tch_h_load': int(status.get('tch_h_load', 0)),
            'tch_h_max': int(status.get('tch_h_max', 0)),
            'sdcch8_load': int(status.get('sdcch8_load', 0)),
            'sdcch8_max': int(status.get('sdcch8_max', 0)),
            'tch_f_pdch_load': int(status.get('tch_f_pdch_load', 0)),
            'tch_f_pdch_max': int(status.get('tch_f_pdch_max', 0))
         }

    def get_available_bands(self):
        """Returns a list of band names that are supported
        by osmocom. Note that these are not necessarily
        the bands that are supported by the hardware being used"""
        return ['GSM850', 'GSM900', 'DCS1800', 'PCS1900']

    def get_available_arfcns(self, bts_id):
        """Returns a list of valid ARFCNs for the current band"""
        cur_band = self.show(bts_id)['band']
        valid_arfcns = {'GSM850': list(range(128, 252)),
                        'GSM900': list(range(0,125)) + list(range(955,1024)),
                        'DCS1800': list(range(512,886)),
                        'PCS1900': list(range(512,811))}
        return valid_arfcns[cur_band]

    def running_config(self, bts_id):
        """Return bts running configuration for bts_id"""
        conf = super(BTS, self).running_config()
        return conf['network']['bts'][str(bts_id)]


    def show(self, bts_id):
        """Retreives data returned when issuing the show command
        on the VTTY as a dictionary with data entries corresponding
        to the named regex matching groups in `self.PARSE_SHOW`
        """
        with self.enable_mode():
            resp = self.sendrecv('show bts %s' % bts_id)
        if "can't find BTS" in resp:
            raise ValueError('invalid bts')
        return self._parse_show(resp)

    def set_cell_identity(self, bts_id, identity):
        """Set the cell identity."""
        return self.__set(bts_id, 'cell_identity', identity)

    def set_location_area_code(self, bts_id, lac):
        """Set the LAC"""
        return self.__set(bts_id, 'location_area_code', lac)

    def set_bsic(self, bts_id, bsic):
        """Set the base station id code"""
        return self.__set(bts_id, 'base_station_id_code', bsic)

    def set_band(self, bts_id, band):
        """Set the band"""
        return self.__set(bts_id, 'band', band)

    def set_type(self, bts_id, bts_type):
        """Set the BTS type"""
        return self.__set(bts_id, 'type', bts_type)

    def set_periodic_location_update(self, bts_id, value):
        """Set the T3212 timer for the BTS in minutes <6-1530>.
        The value must be a multiple of 6."""
        return self.__set(bts_id, 'periodic location update', value)

    def __set(self, bts_id, field, value):
        """Generic method for issuing set commands.
        Handles entering the correct configure mode for
        writing BTS settings.
        """
        with self.configure_mode():
            with self.configure('network'):
                with self.configure('bts %s' % bts_id):
                    ret = self.sendrecv('%s %s' % (field, value))
                    if '%' in ret:
                        raise ValueError(ret)
                    self.sendrecv('write') #persist setting
                    return ret
