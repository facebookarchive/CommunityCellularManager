"""Get a subscriber's IMSI from an MSISDN.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from freeswitch import consoleLog
from core.subscriber import subscriber
from core.subscriber.base import SubscriberNotFound


def chat(message, msisdn):
    """Handle chat requests.

    Args:
      msisdn: a subscriber's number
    """
    try:
        imsi = str(subscriber.get_imsi_from_number(msisdn, False))
    except SubscriberNotFound:
        imsi = ''
    consoleLog('info', "Returned Chat: " + imsi + "\n")
    message.chat_execute('set', '_openbts_ret=%s' % imsi)


def fsapi(session, stream, env, msisdn):
    """Handle FS API requests.

    Args:
      msisdn: a subscriber's number
    """
    try:
        imsi = str(subscriber.get_imsi_from_number(msisdn, False))
    except SubscriberNotFound:
        imsi = ''
    consoleLog('info', "Returned FSAPI: " + imsi + "\n")
    stream.write(imsi)


handler = chat
