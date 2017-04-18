"""Utils for Osmocom.
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

def parse_imsi(imsi):
    """This method verifies that the input is a valid imsi,
    ie. it is 14 or 15 digits. It will also strip the prefix "IMSI".
    """
    imsi = imsi[4:] if 'IMSI' in imsi else imsi
    if not str(imsi).isdecimal():
        raise TypeError('IMSI not decimal: %s' % imsi)
    if len(str(imsi)) not in [14, 15]:
        raise ValueError('len(IMSI) invalid')
    return imsi


def format_imsi(imsi_raw):
    """IMSIs should be length 14 or 15 and since osmocom stores them as integers
    test networks with MCC 001 get truncated to 1."""
    imsi = str(imsi_raw)

    # If len(IMSI) is 13 and the MCC starts with 1 this is a test network
    # and we will pad to 15
    if len(imsi) == 13 and imsi[0] == '1':
        imsi = str(imsi).zfill(15)
    return imsi
