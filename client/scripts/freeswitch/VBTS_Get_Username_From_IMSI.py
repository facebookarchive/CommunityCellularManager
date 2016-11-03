"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Get a subscriber's SIP username from an imsi.
We use this because OpenBTS and Osmocom handle SIP user extensions differently.
"""

from freeswitch import consoleLog
from core.subscriber import subscriber
from core.subscriber.base import SubscriberNotFound


def chat(message, imsi):
    """Handle chat requests.

    Args:
      imsi: a subscriber's number
    """
    try:
        name = str(subscriber.get_username_from_imsi(imsi))
    except SubscriberNotFound:
        name = ''
    consoleLog('info', "Returned Chat: " + name + "\n")
    message.chat_execute('set', '_openbts_ret=%s' % name)


def fsapi(session, stream, env, imsi):
    """Handle FS API requests.

    Args:
      imsi: a subscriber's number
    """
    try:
        name = str(subscriber.get_username_from_imsi(imsi))
    except SubscriberNotFound:
        name = ''
    consoleLog('info', "Returned FSAPI: " + name + "\n")
    stream.write(name)
