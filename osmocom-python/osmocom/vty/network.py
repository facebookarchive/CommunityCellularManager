"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import re

from .base import BaseVTY

class Network(BaseVTY):

    def __init__(self, host='127.0.0.1', port=4242, timeout=None):
        super(Network, self).__init__('OpenBSC', host, port, timeout)
        self.PARSE_SHOW = [
            re.compile('BSC is on Country Code (?P<mcc>\d+), Network Code (?P<mnc>\d+) and has (?P<bts_count>\d+) BTS'),
            re.compile('Long network name: \'(?P<long_name>[^\s]+)\''),
            re.compile('Short network name: \'(?P<short_name>[^\s]+)\''),
            re.compile('Authentication policy: (?P<auth_policy>[^\s]+)'),
            re.compile('Location updating reject cause: (?P<lur_reject_cause>\d+)'),
            re.compile('Encryption: (?P<encryption>[^\s]+)'),
            re.compile('NECI \(TCH/H\): (?P<neci>\d+)'),
            re.compile('Use TCH for Paging any: (?P<tch_paging>\d+)'),
            re.compile('RRLP Mode: (?P<rrlp_mode>[^\s]+)'),
            re.compile('MM Info: (?P<mm_info>[^\s]+)'),
            re.compile('Handover: (?P<handover>[^\s]+)'),
            re.compile('Current Channel Load: (?P<channel_load>[^\s]+)')]

    def running_config(self):
        """Return network running configuration"""
        conf = super(Network, self).running_config()
        return conf['network']

    def show(self):
        """Retreives data returned when issuing the show command
        on the VTTY as a dictionary with data entries corresponding
        to the named regex matching groups in `self.PARSE_SHOW`
        """
        with self.enable_mode():
            resp = self.sendrecv('show network')
            return self._parse_show(resp)

    def set_mcc(self, mcc):
        """Set the MCC."""
        return self.__set('network country code', mcc)

    def set_mnc(self, mnc):
        """Set the MNC."""
        return self.__set('mobile network code', mnc)

    def set_short_name(self, name):
        """Set the short name"""
        return self.__set('short name', name)

    def set_long_name(self, name):
        """Set the long name"""
        return self.__set('long name', name)

    def set_handover(self, value):
        """Enable or disable handover"""
        return self.__set('handover', value)

    def set_timer(self, timer, value):
        """Set the value of a timer"""
        return self.__set('timer t%d' % timer, value)

    def __set(self, field, value):
        """Generic method for issuing set commands.
        Handles entering the correct configure mode for
        writing network settings.
        """
        with self.configure_mode():
            with self.configure('network'):
                ret = self.sendrecv('%s %s' % (field, value))
                if '%' in ret:
                    raise ValueError(ret)
                self.sendrecv('write') #persist
                return ret
