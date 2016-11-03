"""Parsing Destinations from phone numbers.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""


def parse_destination(phone_number, destinations):
    """Find the matching destination for a phone number.

    Args:
      phone_number: a string number with no leading '+'
      destinations: a list of Destination instances

    Returns:
      a Destination instance or None if the prefix wasn't found.
    """
    # Get all the prefixes.
    prefixes = [d.prefix for d in destinations]
    # The longest possible prefix is four digits, so we'll start with that as a
    # guess.
    possible_prefix = phone_number[0:4]
    while possible_prefix:
        if possible_prefix in prefixes:
            index = prefixes.index(possible_prefix)
            return destinations[index]
        else:
            # Pop off the last number and try again.
            possible_prefix = possible_prefix[0:-1]
    # Prefix not found.
    return None
