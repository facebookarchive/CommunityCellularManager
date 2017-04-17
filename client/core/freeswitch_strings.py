"""
We have a few strings that are defined in our FS chatplan and dialplan which
need internationalization support.

The way we handle this is via the endaga_i18n script. It's used in a
dialplan/chatplan like so:

    <action application="python" data='endaga_i18n "Your number is %(number)s" % {"number": ${vbts_callerid}}'/>

The result is saved into the $endaga_i18n FS variable for later use.

Note what this does -- it's passing in a string to the script, which in turn
needs to look it up and return some sensible result. This file is where we
actually keep track of the various strings used in the dialplan/chatplan.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import gettext

from ccm.common import currency
import core.config_database

configdb = core.config_database.ConfigDB()

gt = gettext.translation("endaga", configdb['localedir'], [configdb['locale'], "en"]).gettext

# NOTE: (chatplan/01_provisioning) This message is sent when a user tries to register an already registered SIM card.
gt("Already registered with number %(number)s.")

# NOTE: (chatplan/02_unprovisioned) This message is sent when an unprovisioned phone tries to use the network.
gt("Your phone is not provisioned.")

# NOTE: (chatplan/12_credit_check, dialplan/10_credit_check) This message is sent when the user checks their account balance.
gt("Your balance is %(account_bal)s.")

# NOTE: (chatplan/13_number_check, dialplan/11_number_check) This message is sent when the user checks their phone number.
gt("Your number is %(number)s.")

# NOTE: (chatplan/20_error) Sent when the SMS contains bad characters.
gt("Message not sent to %(dest_number)s.")

# NOTE: (dialplan/25_no_money) This message is sent when the user has insufficient funds.
gt("Your account doesn't have sufficient funds.")

# NOTE: (chatplan/22_no_money) This message is sent when the user has insufficient funds for an SMS
gt("Your account doesn't have sufficient funds to send an SMS.")

# NOTE: (chatplan/99_invalid) This message is sent when the SMS is sent to an invalid address.
gt("Invalid Address")

def localize(string_key, params):
    return str(gt(string_key) % params)

def humanize_credits(amount_raw):
    """Given a raw amount from the subscriber registry, this will return a
    human readable Money instance in the local Currency.
    """
    currency_code = configdb['currency_code']
    money = currency.humanize_credits(amount_raw,
                currency.CURRENCIES[currency_code])
    return money

def parse_credits(string):
    """Given a numerical string, this will return a Money instance in the
    local currency.
    """
    currency_code = configdb['currency_code']
    money = currency.parse_credits(string,
                currency.CURRENCIES[currency_code])
    return money
