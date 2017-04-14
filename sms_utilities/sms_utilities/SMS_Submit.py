"""Generating SMS-SUBMIT messages.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import random
import sys

from smspdu import SMS_SUBMIT

from . import SMS_Helper


def gen_tpdu(ref, to, text, empty):
    # TP-PID = 40 ==> short message type 0
    # TP-DCS = c3 ==> disable "other message indicator" and discard message
    if empty:
        text = ""
    TPPID = 0x40 if empty else 0
    TPDCS = 0xc3 if empty else 0
    pdu = SMS_SUBMIT.create(None, to, text, tp_pid=TPPID, tp_dcs=TPDCS).toPDU()
    return [pdu]


def gen_rp_header(ref, empty):
    # If 'empty' is true, generates for Empty SMS
    rp_header = [
        "00",  # Message Type = ms->n
        ref,  # Message Reference
        "00",  # RP-originator Address (zero length, no data)
        SMS_Helper.encode_num("0000")  # RP-destination address
    ]
    return rp_header


def gen_msg(to, text, empty=False):
    # Note we are constructing a RPDU which encapsulates a TPDU.
    ref = str(SMS_Helper.to_hex2(random.randint(0, 255)))
    rp_header = gen_rp_header(ref, empty)
    tpdu = gen_tpdu(ref, to, text, empty)
    tp_len = len("".join(tpdu)) / 2  # In octets.
    body = rp_header + [SMS_Helper.to_hex2(tp_len)] + tpdu
    return "".join(body)


if __name__ == '__main__':
    to = "101"
    msg = "Test Message"
    if len(sys.argv) > 2:
        to = sys.argv[1]
        msg = sys.argv[2]
    print(gen_msg(to, msg))
