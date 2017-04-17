# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

import sys

from core.sms import sms

from freeswitch import consoleLog

def chat(message, args):
    try:
        consoleLog('info', "Parsing:%s\n" % message.getBody())
        content = sms.parse_message(message)
        for key, value in list(content.items()):
            consoleLog('info', "Setting %s=%s\n" % (str(key), str(value)))
            message.chat_execute('set', '%s=%s' % (str(key), str(value)))
    except Exception as err:
        consoleLog('err', str(err))
        sys.stderr.write(str(err))
        raise err


def fsapi(session, stream, env, args):
    consoleLog('err', 'Cannot call Parse_SMS from the FS API\n')
    exit(1)
