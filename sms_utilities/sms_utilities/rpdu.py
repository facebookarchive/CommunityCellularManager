"""RPDU message generation.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""


def strip_fs(s):
    if len(s) == 0:
        return s
    if s[-1] in ['f', 'F']:
        return s[:-1]
    else:
        return s


def reverse_byte_order(o):
    i = 0
    res = ''
    while i < len(o):
        res += o[i+1]
        res += o[i]
        i += 2
    return res


def n_bytes(h, n):
    (hex_str, index) = h
    return (hex_str[index:index+n], (hex_str, index+n))


def get_rp_message_type(h):
    return n_bytes(h, 2)


def get_rp_message_reference(h):
    return n_bytes(h, 2)


def get_rp_address(h):
    (num_octets, h) = n_bytes(h, 2)
    num_octets = int(num_octets, 16)
    (rp_dest_address_type, h) = n_bytes(h, 2)
    # Minus for address type, *2 as octets.
    (rp_dest_address, h) = n_bytes(h, (num_octets-1)*2)
    return (rp_dest_address_type,
            strip_fs(reverse_byte_order(rp_dest_address)), h)


def get_rp_destination_address(h):
    return n_bytes(h, 2)


def get_rp_user_data(h):
    (num_octets, h) = n_bytes(h, 2)
    num_octets = int(num_octets, 16)*2
    if (len(h[0]) - h[1]) != num_octets:
        raise Exception("MALFORMED MESSAGE: Bad RP-User-Data length")
    return h


class RPDU:
    def __init__(self, rp_mti, rp_message_reference, rp_originator_address,
            rp_destination_address, user_data,
            rp_destination_address_type="81",
            rp_originator_address_type="81"):
        self.rp_mti = rp_mti
        self.rp_message_reference = rp_message_reference
        self.rp_originator_address = rp_originator_address
        self.rp_destination_address = rp_destination_address
        self.rp_originator_address_type = rp_originator_address_type
        self.rp_destination_address_type = rp_destination_address_type
        self.user_data = user_data

    def toPDU(self):
        return ''.join([self.rp_mti, self.rp_message_reference,
            self.rp_originator_address, self.rp_destination_address,
            self.user_data])

    @classmethod
    def fromPDU(cls, rp_message):
        rp_message = (rp_message, 0)
        (rp_message_type, rp_message) = get_rp_message_type(rp_message)
        (rp_message_reference, rp_message) = (
            get_rp_message_reference(rp_message))
        (rp_originator_address_type, rp_originator_address, rp_message) = (
            get_rp_address(rp_message))
        (rp_dest_address_type, rp_dest_address, rp_message) = (
            get_rp_address(rp_message))

        rp_user_data = get_rp_user_data(rp_message)
        rp_user_data = rp_user_data[0][rp_user_data[1]:]
        return cls(rp_message_type, rp_message_reference,
                   rp_originator_address, rp_dest_address, rp_user_data)

