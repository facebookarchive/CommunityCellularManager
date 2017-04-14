"""SMS parsing.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import sys

from smspdu import SMS_SUBMIT

from .rpdu import RPDU
from .SMS_Helper import clean, smspdu_charstring_to_hex


def parse(rp_message):
    rpdu = RPDU.fromPDU(rp_message)
    sms_submit = SMS_SUBMIT.fromPDU(rpdu.user_data, rpdu.rp_originator_address)
    exports = [
        ("vbts_text", sms_submit.user_data),
        ("vbts_tp_user_data", smspdu_charstring_to_hex(sms_submit.tp_ud)),
        ("vbts_tp_data_coding_scheme", sms_submit.tp_dcs),
        ("vbts_tp_protocol_id", sms_submit.tp_pid),
        ("vbts_tp_dest_address", sms_submit.tp_da),
        ("vbts_tp_dest_address_type", sms_submit.tp_toa),
        ("vbts_tp_message_type", sms_submit.tp_mti),
        ("vbts_rp_dest_address", rpdu.rp_destination_address),
        ("vbts_rp_originator_address", rpdu.rp_originator_address),
        ("vbts_rp_originator_address_type", rpdu.rp_originator_address_type),
        ("vbts_rp_message_reference", rpdu.rp_message_reference),
        ("vbts_rp_message_type", rpdu.rp_mti)
    ]
    exports = [(x, clean(y)) for (x, y) in exports]
    return exports

if __name__ == '__main__':
    h = "001000038100000e05df04810011000005cbb7fb0c02"
    if len(sys.argv) > 1:
        h = sys.argv[1]
    print(parse(h))
