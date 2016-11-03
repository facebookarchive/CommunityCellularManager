"""Get a subscriber's port via their IMSI.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from freeswitch import consoleLog

from core.subscriber import subscriber


def chat(message, imsi):
    """Handle chat requests.

    Args:
      imsi: a subscriber's IMSI
    """
    port = str(subscriber.get_port(imsi))
    consoleLog('info', "Returned Chat: " + port + "\n")
    message.chat_execute('set', '_openbts_ret=%s' % port)


def fsapi(session, stream, env, imsi):
    """Handle FS API requests.

    Args:
      imsi: a subscriber's IMSI
    """
    port = str(subscriber.get_port(imsi))
    consoleLog('info', "Returned FSAPI: " + port + "\n")
    stream.write(port)
