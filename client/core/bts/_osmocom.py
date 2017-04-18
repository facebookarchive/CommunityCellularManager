# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

import sys

from osmocom.vty.bts import BTS
from osmocom.vty.network import Network
from osmocom.vty.trx import TRX
from osmocom.vty.subscribers import Subscribers

from core.config_database import ConfigDB
from core.bts.base import BaseBTS
from core.exceptions import BSSError
from core.service import Service

class OsmocomBTS(BaseBTS):

    REGISTERED_AUTH_VALUES = [1, ] # 0 = camped, open reg. 1 = camped, auth'd
    DEFAULT_BTS_ID = 0
    DEFAULT_TRX_ID = 0
    """Osmocom services, order does matter. The dependency chart
       looks like this:

       osmo-trx ---\
                     -- osmo-bts-trx --\
       osmocom-nitb /                   osmo-pcu -- openggsn -- osmo-sgsn
                    \
                     -- osmo-sip-connector -- mod_sofia (freeswitch)
                     -- mod_smpp (freeswitch)
    """
    SERVICES = [Service.SupervisorService('osmo-trx'),
                Service.SystemService('osmocom-nitb'),
                Service.SystemService('osmo-bts-trx'),
                Service.SystemService('osmo-sip-connector'),
                Service.SystemService('osmo-pcu'),
                Service.SystemService('openggsn'),
                Service.SystemService('osmo-sgsn')]

    def __init__(self):
        self.conf = ConfigDB()
        self.subscribers = Subscribers(host=self.conf['bts.osmocom.ip'],
            port=self.conf['bts.osmocom.bsc_vty_port'],
            hlr_loc=self.conf['bts.osmocom.hlr_loc'],
            timeout=self.conf['bss_timeout'])
        self.network = Network(host=self.conf['bts.osmocom.ip'],
            port=self.conf['bts.osmocom.bsc_vty_port'],
            timeout=self.conf['bss_timeout'])
        self.bts = BTS(host=self.conf['bts.osmocom.ip'],
            port=self.conf['bts.osmocom.bsc_vty_port'],
            timeout=self.conf['bss_timeout'])
        self.trx = TRX(host=self.conf['bts.osmocom.ip'],
            port=self.conf['bts.osmocom.bsc_vty_port'],
            timeout=self.conf['bss_timeout'])

    def set_factory_config(self):
        pass

    def get_camped_subscribers(self, access_period=0, auth=1):
        try:
            with self.subscribers as s:
                return s.camped_subscribers(access_period, auth)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_load(self):
        try:
            with self.bts as b:
                load = b.get_load(self.DEFAULT_BTS_ID)
                # If we weren't able to read any channel load
                # the transceiver is not running
                if sum(load.values()) == 0:
                    raise BSSError("TRX not running")
                return load
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_noise(self):
        return {'some_noise_stats_here_tbd': 0}

    def set_mcc(self, mcc):
        """Set MCC"""
        try:
            with self.network as n:
                return n.set_mcc(mcc)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_mnc(self, mnc):
        """Set MNC"""
        try:
            with self.network as n:
                return n.set_mnc(mnc)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_short_name(self, short_name):
        """Set beacon short name"""
        try:
            with self.network as n:
                return n.set_short_name(short_name)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_open_registration(self, expression):
        """Set a regular expression matching IMSIs
        that can camp to the network"""
        raise NotImplementedError("Osmocom needs to implement this. Only has token auth for Ad-Hoc networks.")

    def set_timer(self, timer, value):
        """Set a particular BTS timer.
        The only timer in use currently is T3212"""
        try:
            if str(timer) == '3212':
                with self.bts as b:
                    return b.set_periodic_location_update(self.DEFAULT_BTS_ID, value)
            else:
                with self.network as n:
                    return n.set_timer(timer, value)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_band(self, band):
        """Set the GSM band of default BTS"""
        try:
            with self.bts as b:
                return b.set_band(self.DEFAULT_BTS_ID, band)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_arfcn_c0(self, arfcn):
        """Set the ARFCN of the first carrier."""
        try:
            with self.trx as t:
                return t.set_arfcn(self.DEFAULT_BTS_ID, self.DEFAULT_TRX_ID, arfcn)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_mcc(self):
        try:
            with self.network as n:
                return n.show()['mcc']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_mnc(self):
        try:
            with self.network as n:
                return n.show()['mnc']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_short_name(self):
        try:
            with self.network as n:
                return n.show()['short_name']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_open_registration(self):
        raise NotImplementedError()

    def get_timer(self, timer):
        try:
            if str(timer) == '3212':
                with self.bts as b:
                    return b.running_config(self.DEFAULT_BTS_ID)['periodic location update']
            else:
                with self.network as n:
                    return n.running_config()['timer t%d' % timer]
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_available_bands(self):
        try:
            with self.bts as b:
                return b.get_available_bands()
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_available_arfcns(self):
        """Returns a list of available ARFCNs for the default BTS"""
        try:
            with self.bts as b:
                return b.get_available_arfcns(self.DEFAULT_BTS_ID)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_band(self):
        try:
            with self.bts as b:
                return b.show(self.DEFAULT_BTS_ID)['band']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_arfcn_c0(self):
        try:
            with self.trx as t:
                return t.show(self.DEFAULT_BTS_ID, self.DEFAULT_TRX_ID)['arfcn']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_gprs_usage(self, target_imsi=None):
        """Get all available GPRS data, or that of a specific IMSI (experimental).

        Will return a dict of the form: {
          'ipaddr': '192.168.99.1',
          'downloaded_bytes': 200,
          'uploaded_bytes': 100,
        }

        Or, if no IMSI is specified, multiple dicts like the one above will be
        returned as part of a larger dict, keyed by IMSI.

        Args:
          target_imsi: the subsciber-of-interest
        """
        raise NotImplementedError()

    def get_versions(self):
        #custom keys for this BTS type
        versions = BaseBTS.get_versions(self)
        versions['osmocom-public'] = self.conf['gsm_version']
        versions['python-osmocom'] = self.conf['python-gsm_version']
        return versions
