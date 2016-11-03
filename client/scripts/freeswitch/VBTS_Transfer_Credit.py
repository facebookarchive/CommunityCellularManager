# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

from freeswitch import consoleLog

from core.apps import sms_credit_transfer


def chat(message, args):
    consoleLog('info', "Credit transfer: %s\n" % args)
    from_, request = args.split("|", 1)
    sms_credit_transfer.handle_incoming(from_, request)


def fsapi(session, stream, env, args):
    # chat doesn't use msg anyway
    chat(None, args)
