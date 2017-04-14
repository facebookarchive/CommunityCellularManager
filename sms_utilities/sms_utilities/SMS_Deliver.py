"""Generating SMS-DELIVER messages.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import random
import sys

from smspdu import SMS_DELIVER

from . import SMS_Helper


def gen_tpdu(ref, to, fromm, text, empty):
    # See 3GPP TS 23.040 version 11.5.0 Release 11.
    # TP-PID = 40 ==> short message type 0
    # TP-DCS = c3 ==> disable "other message indicator" and discard message
    TPPID = 0x40 if empty else 0
    TPDCS = 0xc3 if empty else 0
    if empty:
        text = ""
    pdu = SMS_DELIVER.create(
        fromm, to, text, tp_pid=TPPID, tp_dcs=TPDCS).toPDU()
    return [pdu]


def gen_rp_header(ref, empty):
    # If 'empty' is true, generates for Empty SMS
    # GSM 4.11: 8.21, 8.22
    rp_header = [
        "01",  # Message Type = n -> ms
        ref,   # Message Reference
        SMS_Helper.encode_num("0000"),
        "00"   # RP-destination address for Service Center
    ]
    return rp_header


def gen_msg(to, fromm, text, empty=False):
    # We are constructing a RPDU which encapsulates a TPDU.
    ref = str(SMS_Helper.to_hex2(random.randint(0, 255)))
    rp_header = gen_rp_header(ref, empty)
    tpdu = gen_tpdu(ref, to, fromm, text, empty)
    tp_len = len("".join(tpdu)) / 2 # in octets
    body = rp_header + [SMS_Helper.to_hex2(tp_len)] + tpdu
    return "".join(body)


if __name__ == '__main__':
    to = "9091"
    fromm = "101"
    msg = "Test Message"
    if len(sys.argv) > 2:
        to = sys.argv[1]
        msg = sys.argv[2]
    print(gen_msg(to, fromm, msg))
