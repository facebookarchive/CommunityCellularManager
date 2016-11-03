"""Utilities for composing SMS messages.

Note that this module imports freeswitch and will thus only work in certain environments.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

class BaseSMS(object):
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
        raise NotImplementedError()

    def send(self, dest, source, body):
        """Send a message via the SMSC addressed using MSISDNs"""
        raise NotImplementedError()

    def send_direct(self, dest, source, body):
        """Send a message directly via the BTS addressed using IMSIs"""
        raise NotImplementedError()
