""" Determine if an MSISDN refers to a camped subscriber.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from freeswitch import consoleLog

from core.exceptions import SubscriberNotFound
from core.subscriber import subscriber
from core.bts import bts

def chat(message, msisdn):
    """Handle chat requests.

    Args:
      msisdn: a subscriber's number
    """
    try:
        imsi = str(subscriber.get_imsi_from_number(msisdn))
    except SubscriberNotFound:
        # If the MSISDN isn't even in the sub registry, it's not camped
        consoleLog('info', "Returned Chat: FALSE\n")
        message.chat_execute('set', '_openbts_ret=FALSE')
        return
    camped = [str(_['imsi']) for _ in bts.active_subscribers()]
    res = "TRUE" if imsi in camped else "FALSE"
    consoleLog('info', "Returned Chat: %s\n" % res)
    message.chat_execute('set', '_openbts_ret=%s' % res)


def fsapi(session, stream, env, msisdn):
    """Handle FS API requests.

    Args:
      msisdn: a subscriber's number
    """
    try:
        imsi = str(subscriber.get_imsi_from_number(msisdn))
    except SubscriberNotFound:
        # If the MSISDN isn't even in the sub registry, it's not camped
        consoleLog('info', "Returned FSAPI: FALSE\n")
        stream.write('FALSE')
        return
    camped = [str(_['imsi']) for _ in bts.active_subscribers()]
    res = "TRUE" if imsi in camped else "FALSE"
    consoleLog('info', "Returned FSAPI: %s\n" % res)
    stream.write(res)
