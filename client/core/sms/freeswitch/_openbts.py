# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

import freeswitch
import openbts
import sms_utilities

from core.config_database import ConfigDB
from core.sms.base import BaseSMS

SMS_LENGTH = 160

def chunk_sms(body):
    res = []
    i = 0
    while (i + SMS_LENGTH) < len(body):
        res.append(body[i:i+SMS_LENGTH])
        i += SMS_LENGTH
    res.append(body[i:])
    return res

class OpenBTSSMS(BaseSMS):
    def __init__(self):
        self.conf = ConfigDB()
        self.smqueue = openbts.components.SMQueue(
            socket_timeout=self.conf['bss_timeout'],
            cli_timeout=self.conf['bss_timeout'])

    def parse_message(self, message):
        """Take a FS message and return a dictionary with the keys:
              vbts_text
              vbts_tp_user_data
              vbts_tp_data_coding_scheme
              vbts_tp_protocol_id
              vbts_tp_dest_address
              vbts_tp_dest_address_type
              vbts_tp_message_type
              vbts_rp_dest_address
              vbts_rp_originator_address
              vbts_rp_originator_address_type
              vbts_rp_message_reference
              vbts_rp_message_type
        """
        content = sms_utilities.SMS_Parse.parse(message.getBody())
        return dict(content)

    def send(self, to, fromm, body, empty=False):
        """Send a message via the SMSC addressed using MSISDNs"""
        for chunk in chunk_sms(body):
            event = freeswitch.Event("CUSTOM", "SMS::SEND_MESSAGE")
            event.addHeader("proto", "sip")
            event.addHeader("dest_proto", "sip")
            event.addHeader("from", fromm)
            from_full = ("sip:" + fromm + "@" +
                         freeswitch.getGlobalVariable("domain"))
            event.addHeader("from_full", from_full)
            sip_my_ip = self.smqueue.read_config('SIP.myIP').data['value']
            sip_my_port = self.smqueue.read_config('SIP.myPort').data['value']
            to_full = str(freeswitch.getGlobalVariable("smqueue_profile") +
                          "/sip:smsc@" + sip_my_ip + ":" + sip_my_port)
            event.addHeader("to", to_full)
            event.addHeader("subject", "SIMPLE_MESSAGE")
            event.addHeader("type", "application/vnd.3gpp.sms")
            event.addHeader("hint", "the hint")
            event.addHeader("replying", "false")
            event.addBody(sms_utilities.SMS_Submit.gen_msg(to, chunk, empty))
            event.fire()


    def send_direct(self, to, fromm, body, empty=False):
        """Send a message directly via the BTS addressed using IMSIs"""
        for chunk in chunk_sms(body):
            imsi = to[0]
            ipaddr = to[1]
            port = to[2]
            body = (sms_utilities.SMS_Deliver.gen_msg(
                to, fromm, chunk, empty).upper())
            freeswitch.consoleLog(
                'info', 'Message body is: \'' + str(chunk) + '\'\n')
            event = freeswitch.Event("CUSTOM", "SMS::SEND_MESSAGE")
            event.addHeader("proto", "sip")
            event.addHeader("dest_proto", "sip")
            event.addHeader("from", fromm)
            from_full = ("sip:" + fromm + "@" +
                         freeswitch.getGlobalVariable("domain"))
            event.addHeader("from_full", from_full)
            to_full = str(freeswitch.getGlobalVariable("smqueue_profile") +
                          "/sip:"+ str(imsi) + "@" + ipaddr + ":" + str(port))
            event.addHeader("to", to_full)
            event.addHeader("subject", "SIMPLE_MESSAGE")
            event.addHeader("type", "application/vnd.3gpp.sms")
            event.addHeader("hint", "the hint")
            event.addHeader("replying", "false")
            event.addBody(body)
            event.fire()
