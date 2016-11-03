# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

from freeswitch import consoleLog

from core import config_database

def chat(message, args):
    """
    Args: string config key

    Does not return anything, but sets the variable "_endaga_ret" to the value
    of the config key in the ConfigDB if it exists, or to the empty string
    otherwise.
    """
    cdb = config_database.ConfigDB()
    key = args.strip()
    try:
        res = cdb[key].strip()
    except KeyError:
        res = ""
    consoleLog('info', "ConfigDB Chat %s -> %s" % (key, res))
    message.chat_execute('set', '_endaga_ret=%s' % res)


def fsapi(session, stream, env, args):
    """
    Args: string config key

    Does not return anything, but writes to output the value of the config key
    in the ConfigDB if it exists, or to the empty string otherwise.
    """
    cdb = config_database.ConfigDB()
    key = args.strip()
    try:
        res = cdb[key].strip()
    except KeyError:
        res = ""
    consoleLog('info', "ConfigDB FSAPI %s -> %s" % (key, res))
    stream.write(res)
