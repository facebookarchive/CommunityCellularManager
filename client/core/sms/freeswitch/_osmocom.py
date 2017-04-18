# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

import freeswitch
import osmocom

from core.config_database import ConfigDB
from core.sms.base import BaseSMS

from osmocom.vty.subscribers import Subscribers

class OsmocomSMS(BaseSMS):

    def __init__(self):
        self.conf = ConfigDB()
        self.subscribers = Subscribers(host=self.conf['bts.osmocom.ip'],
            port=self.conf['bts.osmocom.bsc_vty_port'],
            hlr_loc=self.conf['bts.osmocom.hlr_loc'],
            timeout=self.conf['bss_timeout'])

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
        vbts_dict = {
            'vbts_text': message.getBody(),
            'vbts_tp_user_data': '',
            'vbts_tp_data_coding_scheme': '',
            'vbts_tp_protocol_id': '',
            'vbts_tp_dest_address': message.getHeader("to_user"),
            'vbts_tp_dest_address_type': '',
            'vbts_tp_message_type': '',
            'vbts_rp_dest_address': '',
            'vbts_rp_originator_address': message.getHeader("from_user"),
            'vbts_rp_originator_address_type': '',
            'vbts_rp_message_reference': '',
            'vbts_rp_message_type': ''}
        return vbts_dict

    def send(self, dest, source, body):
        """Send a message via the SMSC addressed using MSISDNs"""
        event = freeswitch.Event("CUSTOM", "SMS::SEND_MESSAGE")
        event.addHeader("proto", "smpp")
        event.addHeader("dest_proto", "smpp")
        event.addHeader("smpp_gateway", "openbsc")
        event.addHeader("from", source)
        event.addHeader("from_user", source)
        event.addHeader("dest_addr_npi", "NPI_ISDN_E163_E164")
        event.addHeader("to_user", dest)
        event.addBody(body)
        event.fire()


    def send_direct(self, dest, source, body):
        """Send a message directly via the BTS addressed using IMSIs"""
        imsi = dest[0]
        ipaddr = dest[1]
        port = dest[2]
        # event = freeswitch.Event("CUSTOM", "SMS::SEND_MESSAGE")
        # event.addHeader("proto", "smpp")
        # event.addHeader("dest_proto", "smpp")
        # event.addHeader("smpp_gateway", "openbsc")
        # event.addHeader("from", source)
        # event.addHeader("from_user", source)

        # this allows you to address an IMSI and needs to be implemented in mod_smpp.c
        # event.addHeader("dest_addr_npi", "NPI_Land_Mobile_E212")

        # event.addHeader("to_user", imsi)
        # event.addBody(body)
        # event.fire()

        # workaround for now, send using the TTY
        # but the source address must also be a subscriber
        # so the source imsi is dest imsi
        with self.subscribers as s:
            return s.sms(imsi, imsi, body)
