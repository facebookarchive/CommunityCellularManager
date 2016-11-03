# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

from freeswitch import consoleLog

from core.sms import sms


def chat(message, args):
    args = args.split('|')
    if len(args) < 5:
        consoleLog('err', 'Missing Args: got %s\n' % str(args))
        exit(1)
    to = args[0]
    ipaddr = args[1]
    port = args[2]
    fromm = args[3]
    text = args[4]
    if ((not to or to == '')
            or (not fromm or fromm == '')):
        consoleLog('err', 'Malformed Args: got %s\n' % str(args))
        exit(1)
    consoleLog('info', 'Args: ' + str(args) + '\n')

    res = sms.send_direct((to, ipaddr, port), fromm, text)
    consoleLog('info', 'Result: ' + str(res) + '\n')

def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)
