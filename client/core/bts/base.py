"""BTS utility methods.

This module probes the radio stack for metrics and subscriber presensce.

The appropriate module (Osmocom vs OpenBTS) is loaded on runtime according
to the system configuration.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import time

from ccm.common import logger
from core import VERSION
from core.config_database import ConfigDB

class BaseBTS(object):
    # list of authorization values that count as active/camped
    REGISTERED_AUTH_VALUES = [1,]
    # services that manage the BTS, a list of Service instances
    SERVICES = []

    def __init__(self):
        self.conf = ConfigDB()

    def restart(self):
        """A generic command to restart bts."""
        for s in self.SERVICES:
            s.restart()

    def set_factory_config(self):
        """
        Called on system initialization to set up the radio for first
        use. Should calibrate and set the correct band, arfcn.

        Returns:
            Whether or not need to restart `SERVICES`
        """
        raise NotImplementedError()

    def active_subscribers(self, reg_period=None, auth_class=None):
        """Gathers all camped subscribers from the BSS. Camped subscribers are
        defined as subscribers who have registered (i.e., sent a LUR) in the
        last REG_PERIOD seconds, and who are authorized on the network.

        Args:
            reg_period: # seconds to use as active threshold. Default is
                None, which uses the value of the T3212 timer. This is almost
                always what you want to use, since phones will only send LURs
                as often as that parameter.
            auth_class: A list of auth classes to use. Each implementation
                specifies its own defaults.
        """
        if not reg_period:
            t3212 = int(self.get_timer('3212')) # fail if this isn't defined
            reg_period = t3212 * 60 # t3212 is defined in minutes, we want sec

        if not auth_class:
            # Auth class varies by implementation.
            auth_class = self.REGISTERED_AUTH_VALUES

        camped_subscribers = []
        now = time.time()
        for c in auth_class:
            auth_subs = self.get_camped_subscribers(reg_period, c)
            for entry in auth_subs:
                imsi = "IMSI%s" % entry['IMSI']
                imei = "null" if not "IMEI" in entry else entry['IMEI']
                last_seen_secs = now - int(entry['ACCESSED'])
                camped_subscribers.append({
                    'imsi': imsi,
                    'imei': imei,
                    'auth_class': str(c),
                    'last_seen_secs': last_seen_secs
                })

        return camped_subscribers

    def get_camped_subscribers(self, access_period=0, auth=1):
        """Gets all active subscribers from the TMSI table.

        TODO: this should support multiple auth values; all camped subs are
        actually a combination of 1, 2, and sometimes 3 depending on openbts
        combination. in general, it's alright for us to use just 1.

        Args:
          access_period: fetches all entries with ACCESS < access_period
                             (default=0 filter off)
          auth: fetches all entries with AUTH = auth
                  Unauthorized = 0
                  Authorized by registrar (default) = 1
                  Open registration, not in sub db = 2
                  Failed open registration = 3

        Returns a list subscriber objects with the following values:
           IMSI, TMSI, IMEI, AUTH, CREATED, ACCESSED, TMSI_ASSIGNED

        See section 4.3 of the OpenBTS 4.0 Manual for more fields.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_load(self):
        """Aggregates BTS load information as a dictionary

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_noise(self):
        """Aggregates BTS noise environment as a dictionary.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_available_bands(self):
        """Return a list of bands supported by the BTS

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_available_arfcns(self):
        """Return a list of available ARFCNs that are available
        on the current band

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def set_mcc(self, mcc):
        """Set MCC

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def set_mnc(self, mnc):
        """Set MNC

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def set_short_name(self, short_name):
        """Set beakon short name

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def set_open_registration(self, expression):
        """Set a regular expression matching IMSIs
        that can camp to the network

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def set_timer(self, timer, value):
        """Set a particular BTS timer.
        The only timer in use currently is T3212

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def set_band(self, band):
        """Set the GSM band

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def set_arfcn_c0(self, arfcn):
        """Set the ARFCN of the first carrier.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_mcc(self):
        """Get the network MCC.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_mnc(self):
        """Get the network MNC.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_short_name(self):
        """Get the network short name.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_open_registration(self):
        """Get the network OpenRegistration value.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_timer(self, timer):
        """Get a network timer value.

        Args:
            timer: the number of the timer to get

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_band(self):
        """Get the band the network is operating on.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_arfcn_c0(self):
        """Get the ARFCN of the first carrier.

        Raises:
            BSSError if the operation failed
        """
        raise NotImplementedError()

    def get_versions(self):
        """ Get the version of software on this BTS
        """
        return {
            'endaga': self.conf.get('endaga_version', ''),
            'freeswitch': self.conf.get('freeswitch_version', ''),
            'type' : self.conf['bts.type'],
            'gsm': self.conf.get('gsm_version', ''),
            'python-endaga-core': VERSION,
            'python-gsm': self.conf.get('python-gsm_version', ''),
            #legacy ones for backwards compatibility
            'python-openbts' : None,
            'openbts-public' : None,
        }

    def process_bts_settings(self, data_dict):
        """Process bts settings.

        TODO: We should revisit how configs are stored on cloud
        """
        settings_map = {
            'GSM.Identity.MCC':
                {'get': self.get_mcc,
                 'set': self.set_mcc},
            'GSM.Identity.MNC':
                {'get': self.get_mnc,
                 'set': self.set_mnc},
            'GSM.Identity.ShortName':
                {'get': self.get_short_name,
                 'set': self.set_short_name},
            'Control.LUR.OpenRegistration':
                {'get': self.get_open_registration,
                 'set': self.set_open_registration},
            'GSM.Radio.C0':
                {'get': self.get_arfcn_c0,
                 'set': self.set_arfcn_c0},
            'GSM.Radio.Band':
                {'get': self.get_band,
                 'set': self.set_band},
            'GSM.Timer.T3212':
                {'get': lambda: self.get_timer('3212'),
                 'set': lambda minutes: self.set_timer('3212', minutes)},
        }
        for (key, val) in list(data_dict.items()):
            try:
                cur_val = settings_map[key]['get']()
                if cur_val != val:
                    settings_map[key]['set'](val)
                    logger.info("Changed bts setting: %s = %s (was %s)" %
                                (key, val, cur_val))
            except Exception as e:
                    logger.error("Failed to process openbts setting"
                                 "(%s): %s = %s" % (e, key, val))
