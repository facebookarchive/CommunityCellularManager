"""FS interconnect.

Note that this module imports freeswitch and will thus only work in certain
environments.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from ESL import ESLconnection

from core import number_utilities


class freeswitch_ic(object):
    """FS interconnect."""

    def __init__(self, conf):
        self.conf = conf

    def _send_raw_to_freeswitch_cli(self, cmd):
        con = ESLconnection(self.conf['fs_esl_ip'], self.conf['fs_esl_port'],
                            self.conf['fs_esl_pass'])
        if con.connected():
            con.api(cmd)
            return True
        return False

    def send_to_number(self, to, from_, body, to_country=None,
            from_country=None):
        """Send properly-formatted numbers to FreeSwitch.

        Internally, our canonical format is E.164 without the leading plus (due
        to OpenBTS's inability to handle the + symbol).
        """
        if to_country:
            to = number_utilities.convert_to_e164(to, to_country)
        if from_country:
            from_ = number_utilities.convert_to_e164(from_, from_country)
        to = number_utilities.strip_number(to)
        from_ = number_utilities.strip_number(from_)
        return self._send_raw_to_freeswitch_cli(
                   str("python VBTS_Send_SMS %s|%s|%s" % (to, from_, body)))

    def send_to_imsi(self, to, ipaddr, port, from_, body):
        """Send a message directly to an IMSI. These messages will go directly to
        BTS, so if the message fails to send, it will not be retried."""
        return self._send_raw_to_freeswitch_cli(
                   str("python VBTS_Send_SMS_Direct %s|%s|%s|%s|%s" %
                       (to, ipaddr, port, from_, body)))
