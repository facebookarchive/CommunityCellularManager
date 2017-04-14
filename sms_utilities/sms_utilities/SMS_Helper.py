"""Some utilities.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import string
import sys


def to_hex2(i):
    """Converts an integer to hex form (with 2 digits)."""
    tmp = hex(i)[2:]
    if len(tmp) == 1:
        return "0" + tmp
    else:
        return tmp


def encode_num(num):
    """Jumble the number. i.e. 123 --> "321f"."""
    snuml = list(str(num))
    if len(snuml)%2 == 1:
        snuml += 'f'
    for i in range(len(snuml)):
        if i % 2 == 0:
            snuml[i], snuml[i+1] = snuml[i+1], snuml[i]
    # Below, ext=1 for some reason; use unknown numbering type, unknown
    # numbering plan.
    enc_num = (
        to_hex2(len(snuml)/2 + 1) +  # length of number
        "81" +
        ''.join(snuml)
    )
    return enc_num


def clean(s):
    if isinstance(s, str):
        return filter(lambda x: x in string.printable, s).strip()
    elif isinstance(s, int):
        return "%X" % s
    else:
        return s


def smspdu_charstring_to_hex(string):
    return ''.join(["%02X" % ord(c) for c in string])


if __name__ == '__main__':
    # Jumble the number. i.e. 123 --> "321f".
    to = "1234567"
    if len(sys.argv) > 1:
        to = sys.argv[1]
    print(encode_num(to))
