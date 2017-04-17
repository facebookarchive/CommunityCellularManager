# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

import json

from freeswitch import consoleLog

from core import freeswitch_strings


def parse(args):
    """
    The format of the arguments must be:

        This is some %(word)s string.|{'word': 1234}
        This is some string.

    The first argument is required; the second argument is not
    required. This will return the first argument and either the
    second as a dictionary or an empty dictionary if the second
    isn't present.
    """

    res = args.split('|', 1)
    if len(res) == 1:
        return args, {}
    else:
        return res[0], json.loads(res[1])

def localize(args):
    strkey, params = parse(args)

    # do the localization lookup
    res = freeswitch_strings.localize(strkey, params)
    consoleLog('info', "Localizing %s: %s" % (args, res))
    return res

def chat(message, args):
    res = localize(args)
    message.chat_execute('set', '_localstr=%s' % res)

def fsapi(session, stream, env, args):
    res = localize(args)
    if isinstance(session, str):
        # we're in the FS CLI, so no session object
        consoleLog('info', "No session; otherwise would set _localstr=%s" % res)
    else:
        session.execute("set", "_localstr=%s" % res)

def handler(session, args):
    res = localize(args)
    session.execute("set", "_localstr=%s" % res)
