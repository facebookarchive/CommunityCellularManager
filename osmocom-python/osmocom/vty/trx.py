"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import re

from .base import BaseVTY

class TRX(BaseVTY):

    def __init__(self, host='127.0.0.1', port=4242, timeout=None):
        super(TRX, self).__init__('OpenBSC', host, port, timeout)
        self.PARSE_SHOW = [
            re.compile('TRX (?P<id>\d+) of BTS (?P<bts_id>\d+) is on ARFCN (?P<arfcn>\d+)'),
            re.compile('Description: (?P<description>[^\s]+)'),
            re.compile('RF Nominal Power: (?P<nominal_power>-?\d+) dBm, reduced by (?P<attenuation>-?\d+) dB, resulting BS power: (?P<power>-?\d+) dBm')]

    def set_arfcn(self, bts_id, trx_id, arfcn):
        """Set the ARFCN"""
        return self.__set(bts_id, trx_id, 'arfcn', arfcn)

    def show(self, bts_id, trx_id):
        """Retreives data returned when issuing the show command
        on the VTTY as a dictionary with data entries corresponding
        to the named regex matching groups in `self.PARSE_SHOW`
        """
        with self.enable_mode():
            resp = self.sendrecv('show trx %s %s' % (bts_id, trx_id))
        if "can't find" in resp:
            raise ValueError('invalid trx')
        return self._parse_show(resp)

    def running_config(self, bts_id, trx_id):
        """Return trx running configuration for bts_id and trx_id"""
        conf = super(TRX, self).running_config()
        return conf['network']['bts'][str(bts_id)]['trx'][str(trx_id)]

    def __set(self, bts_id, trx_id, field, value):
        """Generic method for issuing set commands.
        Handles entering the correct configure mode for
        writing TRX settings.
        """
        with self.configure_mode():
            with self.configure('network'):
                with self.configure('bts %s' % bts_id):
                    with self.configure('trx %d' % trx_id):
                        ret = self.sendrecv('%s %s' % (field, value))
                        if '%' in ret:
                            raise ValueError(ret)
                        self.sendrecv('write') #persist setting
                        return ret
