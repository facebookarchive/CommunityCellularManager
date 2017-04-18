# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

import delegator
import errno
import os
import sys

import openbts
from openbts.exceptions import TimeoutError

from ccm.common import logger
from core.config_database import ConfigDB

from core.bts.base import BaseBTS
from core.exceptions import BSSError
from core.service import Service

class OpenBTSBTS(BaseBTS):

    REGISTERED_AUTH_VALUES = [1, 2] # 0=reject, 1=open reg auth'd, 2=auth'd
    SERVICES = [Service.SupervisorService('openbts'),
                Service.SupervisorService('smqueue'),
                Service.SupervisorService('sipauthserve'),
                Service.SupervisorService('gprsd')]

    def __init__(self):
        self.conf = ConfigDB()
        self.openbts = openbts.components.OpenBTS(
            socket_timeout=self.conf['bss_timeout'],
            cli_timeout=self.conf['bss_timeout'])

    def restart(self):
        """An openbts specific command to restart the bts."""
        delegator.run("sudo killall transceiver")

        # If the pid file specified doesn't match a running instance of the
        # process, remove the PID file. This is a workaround for a recurring
        # OpenBTS issue we see. Note, caller must have permissions to remove file.
        # Determine PIDs associated with pname
        path="/var/run/OpenBTS.pid"
        cmd = delegator.run("ps -A | grep OpenBTS")
        if cmd.return_code != 0:
            output = ''
        else:
            output = cmd.out
        pids = []
        for line in output.split('\n'):
            try:
                pids.append(int(line.strip().split()[0]))
            except ValueError:
                continue # not a pid, so ignore it
            except IndexError:
                continue # malformed, ignore

        try:
            with open(path, "r") as f:
                pid = int(f.read().strip())
                if pid not in pids:
                    os.remove(path)
        except IOError as e:
            # ignore ENOENT (pid file doesn't exist)
            if e.errno != errno.ENOENT:
                raise

        # now restart openbts
        Service.SupervisorService("openbts").restart()

    def set_factory_config(self):
        """
        Verifies that OpenBTS TRX frequency offset settings are set to factory
        defaults. This is only necessary for RAD1-based systems.

        If not set to defaults, we need to update OpenBTS. First, we use the
        `freqcorr` command to immediately update the offset; then, we set the
        proper self.configuration value so we will use that in the future (as this is a
        static variable, it's not enough to just update the self.config).

        The default value is defined as follows. First, we check the self.configDB for a
        "RealTRXFreqOffset" key. If this is defined, we use that. If this is
        not defined, we assume the value listed as default for the
        TRX.RadioFrequencyOffset key in OpenBTS is correct; this comes from the
        trxfactory settings burned into the radio. Unfortunately, some radios from
        Range are not properly calibrated, so we perform that calibration in-house
        and set the RealTRXFreqOffset flag in our own self.config DB. We also don't have
        a script implemented to update the contents of the RAD1 EEPROM, so easier
        to just do this.

        We also change the radio band if necessary -- there's some weirdness in the
        implementation described below. If the band is changed, we must restart
        OpenBTS for those changes to take effect, so we do that here as well.

        Returns:
            Whether or not OpenBTS needs to be restarted

        TODO(shaddi): This does not support non-RAD1 systems, we need to add
        support for UHD.
        """
        restart_required = False

        # First set frequency offset -- only needed for RAD1
        try:
            res = self.openbts.read_config("TRX.RadioFrequencyOffset")
        except TimeoutError as e:
            logger.error("Unable to query OpenBTS, can't set factory defaults!")
            raise BSSError(e)
        try:
            default_offset = self.conf['RealTRXFreqOffset']
        except KeyError:
            default_offset = res.data['defaultValue']
        if default_offset != res.data['value']:
            self.openbts.update_config("TRX.RadioFrequencyOffset",
                                         default_offset)

            # We run this command via the CLI to immediately update the frequency
            # offset.
            r = delegator.run("/OpenBTS/OpenBTSCLI -c 'freqcorr %s'" %
                    (default_offset,), timeout=self.conf['bss_timeout'])
            if r.return_code != 0:
                err = "Error %s: %s" % (r.return_code, " ".join(r.cmd))
                logger.error(err)
                raise BSSError(err)
            logger.notice("Frequency offset update to %s" % default_offset)

        # Set band
        res = self.openbts.read_config("GSM.Radio.Band")
        if res.data['defaultValue'] != res.data['value']:
            # We use delegator to update this value instead of the NodeManager
            # interface because of a weird behavior in self.openbts. We rely on OpenBTS
            # to report what ARFCNs in the band it supports when we read the self.config
            # of GSM.Radio.C0 (specifically the validValues section). If we update
            # the self.config via NodeManager, the GSM.Radio.Band self.config setting would
            # be applied, but then reading the value of GSM.Radio.C0 will still
            # return the previous band's set of valid values! For whatever reason,
            # updating the band setting from the CLI will give us the valid ARFCNs
            # for the new band setting.

            logger.notice("Trying to set radio band from %s to %s" % (res.data['value'], res.data['defaultValue']))
            r = delegator.run("/OpenBTS/OpenBTSCLI -c 'config GSM.Radio.Band %s'" %
                      (res.data['defaultValue'],), timeout=self.conf['bss_timeout'])
            if r.return_code != 0:
                err = "Error %s: %s" % (r.return_code, " ".join(r.cmd))
                logger.error(err)
                raise BSSError(err)

            restart_required = True
            logger.notice("Updated radio band to %s" % res.data['defaultValue'])

        # Set ARFCN to lowest for the band
        res = self.openbts.read_config("GSM.Radio.C0")
        valid_arfcns = [_.split("|")[0] \
                          for _ in res.data['validValues'].split(",")]
        if valid_arfcns[0] != res.data['value']:
            logger.notice("Trying to set radio ARFCN from %s to %s" % (res.data['value'], valid_arfcns[0]))
            self.openbts.update_config("GSM.Radio.C0", valid_arfcns[0])
            logger.notice("Updated ARFCN to %s" % valid_arfcns[0])
            return True

        return restart_required

    def get_camped_subscribers(self, access_period=0, auth=1):
        try:
            return self.openbts.tmsis(access_period, auth)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_load(self):
        try:
            tower_load = self.openbts.get_load()
            return {
                    'sdcch_load': tower_load['sdcch_load'],
                    'sdcch_available': tower_load['sdcch_available'],
                    'tchf_load': tower_load['tchf_load'],
                    'tchf_available': tower_load['tchf_available'],
                    'pch_active': tower_load['pch_active'],
                    'pch_total': tower_load['pch_total'],
                    'agch_active': tower_load['agch_active'],
                    'agch_pending': tower_load['agch_pending'],
                    'gprs_current_pdchs': tower_load['gprs_current_pdchs'],
                    'gprs_utilization_percentage': (
                        tower_load['gprs_utilization_percentage']),
                    }
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)


    def get_noise(self):
        try:
            tower_noise = self.openbts.get_noise()
            return {
                    'noise_rssi_db': tower_noise['noise_rssi_db'],
                    'noise_ms_rssi_target_db': (
                        tower_noise['noise_ms_rssi_target_db']),
                    }
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)


    def set_mcc(self, mcc):
        """Set MCC"""
        try:
            return self.openbts.update_config("GSM.Identity.MCC", mcc)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_mnc(self, mnc):
        """Set MNC"""
        try:
            return self.openbts.update_config("GSM.Identity.MNC", mnc)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_short_name(self, short_name):
        """Set beacon short name"""
        try:
            return self.openbts.update_config("GSM.Identity.ShortName", short_name)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_open_registration(self, expression):
        """Set a regular expression matching IMSIs
        that can camp to the network"""
        try:
            return self.openbts.update_config("Control.LUR.OpenRegistration", expression)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_timer(self, timer, value):
        """Set a particular BTS timer.
        The only timer in use currently is T3212"""
        try:
            return self.openbts.update_config("GSM.Timer.T%s" % str(timer), value)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_band(self, band):
        """Set the GSM band"""
        try:
            return self.openbts.update_config("GSM.Radio.Band", band)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def set_arfcn_c0(self, arfcn):
        """Set the ARFCN of the first carrier."""
        try:
            return self.openbts.update_config("GSM.Radio.C0", arfcn)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_mcc(self):
        try:
            res = self.openbts.read_config("GSM.Identity.MCC")
            return res.data['value']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_mnc(self):
        try:
            res = self.openbts.read_config("GSM.Identity.MNC")
            return res.data['value']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_short_name(self):
        try:
            res = self.openbts.read_config("GSM.Identity.ShortName")
            return res.data['value']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_open_registration(self):
        try:
            res = self.openbts.read_config("Control.LUR.OpenRegistration")
            return res.data['value']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_timer(self, timer):
        try:
            res = self.openbts.read_config("GSM.Timer.T%s" % str(timer))
            return res.data['value']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_available_bands(self):
        try:
            res = self.openbts.read_config("GSM.Radio.Band")
            return res.data['validValues'].split(",")
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_available_arfcns(self):
        try:
            res = self.openbts.read_config("GSM.Radio.C0")
            return res.data['validValues'].split(",")
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_band(self):
        # as per github.com/endaga/openbts/GSM/GSMConfig.cpp:gsmInit()
        # valid keys are: 850,900,1800,1900
        # let's convert those to CCM standard names (e.g., GSM900)
        try:
            res = self.openbts.read_config("GSM.Radio.Band")
            #convert to CCM standard
            return "GSM" + str(res.data['value'])
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_arfcn_c0(self):
        try:
            res = self.openbts.read_config("GSM.Radio.C0")
            return res.data['value']
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_versions(self):
        #custom keys for this BTS type
        versions = BaseBTS.get_versions(self)
        versions['openbts-public'] = self.conf['gsm_version']
        versions['python-openbts'] = self.conf['python-gsm_version'] #hack
        return versions
