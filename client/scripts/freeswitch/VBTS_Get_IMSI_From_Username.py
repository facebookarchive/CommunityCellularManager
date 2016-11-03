"""Get a subscriber's imsi from the SIP username
We use this because OpenBTS and Osmocom handle SIP user extensions differently.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from freeswitch import consoleLog
from core.subscriber import subscriber
from core.subscriber.base import SubscriberNotFound


def chat(message, username):
    """Handle chat requests.

    Args:
      username: a sip username in the HLR
    """
    try:
        imsi = str(subscriber.get_imsi_from_username(username))
    except SubscriberNotFound:
        imsi = ''
    consoleLog('info', "Returned Chat: " + imsi + "\n")
    message.chat_execute('set', '_openbts_ret=%s' % imsi)


def fsapi(session, stream, env, username):
    """Handle FS API requests.

    Args:
      username: a sip username in the hlr
    """
    try:
        imsi = str(subscriber.get_imsi_from_username(username))
    except SubscriberNotFound:
        imsi = ''
    consoleLog('info', "Returned FSAPI: " + imsi + "\n")
    stream.write(imsi)
