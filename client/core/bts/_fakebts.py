# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

import sys
import random
import json
import time

from core.config_database import ConfigDB
from core.bts.base import BaseBTS
from core.exceptions import BSSError

class FakeBTS(BaseBTS):

    # don't run any services
    SERVICES = []

    def __init__(self):
        self.conf = ConfigDB()
        self.defaults = {
            'sddch': 8,
            'tchf': 4,
            'pch': 2,
            'agch': 2,
            'pdch': 2,
            'mnc': "001",
            'mcc': "01",
            'c0': 51,
            'band': "GSM900",
            'shortName': "fakeBTS",
            'openRegistration': ".*",
            'timer.3212': 6,
            'camped': json.dumps([]),
        }

    def __get(self, name):
        db_name = "fakebts." + name
        if name in self.defaults:
            return self.conf.get(db_name, default=self.defaults[name])
        else:
            return self.conf.get(db_name)

    def __set(self, name, value):
        self.conf['fakebts.' + name] = value

    def set_factory_config(self):
        """ Done. """
        pass

    def get_camped_subscribers(self, access_period=0, auth=1):
        #camped is serialized
        camped = json.loads(self.__get('camped'))
        #not a real user, but we always need one
        camped +=  ['IMSI001010000000000']
        res = []
        for camp in camped:
            res.append({'IMSI': camp,
                        'ACCESSED' : time.time(),
                    })
        return res

    def get_load(self):
        return {
            'sdcch_load': random.choice(list(range(0, self.__get('sddch')))),
            'sdcch_available': self.__get('sddch'),
            'tchf_load': random.choice(list(range(0, self.__get('tchf')))),
            'tchf_available': self.__get('tchf'),
            'pch_active': random.choice(list(range(0, self.__get('pch')))),
            'pch_total': self.__get('pch'),
            'agch_active': random.choice(list(range(0, self.__get('agch')))),
            'agch_pending': 0,
            'gprs_current_pdchs': random.choice(list(range(0, self.__get('pdch')))),
            #probably should math this
            'gprs_utilization_percentage': .4,
        }

    def get_noise(self):
        return {
            'noise_rssi_db': 60,
            'noise_ms_rssi_target_db': 80,
        }

    def set_mcc(self, mcc):
        self.__set('mcc', mcc)

    def set_mnc(self, mnc):
        self.__set('mnc', mnc)

    def set_short_name(self, short_name):
        self.__set('shortName', short_name)

    def set_open_registration(self, expression):
        self.__set('openRegistration', expression)

    def set_timer(self, timer, value):
        self.__set('timer.' + timer, value)

    def set_band(self, band):
        self.__set('band', band)

    def set_arfcn_c0(self, arfcn):
        self.__set('c0', arfcn)

    def get_mcc(self):
        return self.__get('mcc')

    def get_mnc(self):
        return self.__get('mnc')

    def get_short_name(self):
        return self.__get('shortName')

    def get_open_registration(self):
        return self.__get('openRegistration')

    def get_timer(self, timer):
        try:
            return self.__get('timer.' + timer)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_available_bands(self):
        return [self.get_band()]

    def get_available_arfcns(self):
        return [self.get_arfcn_c0()]

    def get_band(self):
        return self.__get('band')

    def get_arfcn_c0(self):
        return self.__get('c0')

    def get_versions(self):
        #custom keys for this BTS type
        versions = BaseBTS.get_versions(self)
        versions['fakebts'] = self.conf['gsm_version']
        return versions
