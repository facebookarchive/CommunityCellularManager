"""
Utilities for dealing with currencies and conversions

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

currencies = {
        "IDR": "IDR",
        "USD": "USD",
}

def supported_currencies():
    return tuple(zip(currencies.keys(), currencies.keys()))

"""
Convert an amount given in cents to millicents
"""
def cents2mc(amt):
    if not isinstance(amt, int):
        raise ValueError("Must be an integer value.")
    return 1000 * amt

"""
Convert an amount given in (whole) dollars to millicents
"""
def dollars2mc(amt):
    return 100 * cents2mc(amt)

"""
Convert from millicents to cents (used often for billing). Truncate fractional parts of a cent (so mc2cents(1900) == 1).
"""
def mc2cents(amt):
    return int(amt / 1000)

"""
Convert from the integer representation in the DB to what a human would expect.
"""
def humanize(amt, denom):
    if denom=="USD":
        pass
