"""Parsing UsageEvent reasons.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""


def parse_gprs_reason(reason):
    """Finds the uploaded and downloaded bytes from a GPRS UE reason attribute.

    Args:
    reason: a UsageEvent.reason from a 'gprs' kind of UE, e.g. "gprs_usage: 184
            bytes uploaded, 0 bytes downloaded"

    Returns:
      (uploaded_bytes, downloaded_bytes) as integers
    """
    try:
        up = int(reason.split()[1])
        down = int(reason.split()[4])
    except IndexError:
        # Reason is an empty string.
        up, down = 0, 0
    return up, down
