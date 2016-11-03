"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Determine whether a subscriber is provisioned.
"""

import sys

from freeswitch import consoleLog
from core.subscriber import subscriber

def chat(message, imsi):
    """Handle chat requests.

    Args:
      imsi: a subscriber's authorization
    """
    try:
        auth = subscriber.is_authed(imsi)
    except Exception: # handle all failurs as no auth
        exc_type, exc_value, _ = sys.exc_info()
        consoleLog('error', "%s: %s\n" % (exc_type, exc_value))
        auth = False
    consoleLog('info', "Returned Chat: " + str(auth) + "\n")
    message.chat_execute('set', '_openbts_ret=%s' % auth)


def fsapi(session, stream, env, imsi):
    """Handle FS API requests.

    Args:
      imsi: a subscriber's number
    """
    try:
        auth = subscriber.is_authed(imsi)
    except Exception: # handle all failures as no auth
        exc_type, exc_value, _ = sys.exc_info()
        consoleLog('error', "%s: %s\n" % (exc_type, exc_value))
        auth = False
    consoleLog('info', "Returned FSAPI: " + str(auth) + "\n")
    stream.write(str(auth))
