# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

from freeswitch import consoleLog

from core.freeswitch_strings import humanize_credits

def chat(message, arg):
    """
    Arg: string amount

    Does not return anything, but sets the variable "_endaga_ret" to the value
    of the formatted currency string.
    """
    resp = humanize_credits(int(arg))
    consoleLog('info', "endaga_currency Chat %s -> %s" % (arg, resp))
    message.chat_execute('set', '_endaga_ret=%s' % resp)


def fsapi(session, stream, env, arg):
    """
    Args: string of amount

    Does not return anything, but writes to output the value of the formatted
    currency amount"""
    resp = humanize_credits(int(arg))
    consoleLog('info', "endaga_currency FSAPI %s -> %s" % (arg, resp))
    stream.write(str(resp))

handler = chat
