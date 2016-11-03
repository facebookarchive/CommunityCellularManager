# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

from freeswitch import consoleLog

from core import billing
from core import number_utilities


def chat(message, args):
    """Handles data from the chatplan.

    Args:
      string of the form <account_balance>|<service_type>|<destination_number>
    """
    balance, service_type, destination_number = args.split('|')
    # Sanitize the destination number.
    destination_number = number_utilities.strip_number(destination_number)
    res = str(billing.get_seconds_available(
        int(balance), service_type, destination_number))
    consoleLog('info', "Returned Chat: " + res + "\n")
    message.chat_execute('set', 'service_type=%s' % res)


def fsapi(session, stream, env, args):
    """Handles data from the FS API.

    Args:
      string of the form <account_balance>|<service_type>|<destination_number>
    """
    balance, service_type, destination_number = args.split('|')
    # Sanitize the destination number.
    destination_number = number_utilities.strip_number(destination_number)
    res = str(billing.get_seconds_available(
        int(balance), service_type, destination_number))
    consoleLog('info', "Returned FSAPI: " + res + "\n")
    stream.write(res)
