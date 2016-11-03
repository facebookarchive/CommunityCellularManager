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
    if len(args) < 3:
        consoleLog('err', 'Missing Args\n')
        exit(1)
    to = args[0]
    fromm = args[1]
    text = args[2]
    if ((not to or to == '') or
        (not fromm or fromm == '')):
        consoleLog('err', 'Malformed Args\n')
        exit(1)
    consoleLog('info', 'Args: ' + str(args) + '\n')
    sms.send(to, fromm, text)


def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)

handler = chat
