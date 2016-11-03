"""Given a phone number (local or not) canonicalize it according to how numbers
are stored in the Endaga DB (e164 right now).

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from freeswitch import consoleLog

from core import number_utilities as nu


def chat(message, number):
    """Handle chat requests.

    Args:
      number: the number you want canonicalized
    """
    canon = nu.canonicalize(number)
    consoleLog('info', "Returned Chat: " + canon + "\n")
    message.chat_execute('set', '_openbts_ret=%s' % canon)


def fsapi(session, stream, env, number):
    """Handle FS API requests.

    Args:
      number: the number you want canonicalized
    """
    canon = nu.canonicalize(number)
    consoleLog('info', "Returned FSAPI: " + canon + "\n")
    stream.write(canon)

handler = chat
