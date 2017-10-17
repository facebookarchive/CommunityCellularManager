"""Application logic for the SMS credit transfer service.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import gettext
import os
import random
import re
import sqlite3
import time


from core import config_database
from core import events
from core import freeswitch_strings
from core.sms import sms
from core.subscriber import subscriber
from core.exceptions import SubscriberNotFound


config_db = config_database.ConfigDB()
gt = gettext.translation("endaga", config_db['localedir'],
                         [config_db['locale'], "en_US"]).gettext


def _init_pending_transfer_db():
    """Create the pending transfers table if it doesn't already exist."""
    db_create_str = (
        "CREATE TABLE pending_transfers (code VARCHAR(5) PRIMARY KEY,"
        " time FLOAT, from_acct INTEGER, to_acct INTEGER, amount INTEGER);")
    try:
        with open(config_db['pending_transfer_db_path']):
            pass
    except IOError:
        db = sqlite3.connect(config_db['pending_transfer_db_path'])
        db.execute(db_create_str)
        db.commit()
        db.close()
        # Make the DB world-writable.
        os.chmod(config_db['pending_transfer_db_path'], 0o777)


def process_transfer(from_imsi, to_imsi, amount):
    """Process a transfer request.

    Args:
      from_imsi: the sender's IMSI
      to_imsi: the recipient's IMSI
      amount: an amount of credit to add (type?)

    Returns:
      boolean indicating success
    """
    # Error when user tries to transfer to his own account
    if from_imsi == to_imsi:
        return False, gt("Transaction Failed. Sharing load to " 
                         "your own account is not allowed.")
    from_balance = int(subscriber.get_account_balance(from_imsi))
    # Error when user tries to transfer more credit than they have.
    if not from_balance or from_balance < amount:
        return False, gt("Your account doesn't have sufficient funds for"
                         " the transfer.")
    # Error when user tries to transfer to a non-existent user.
    #       Could be 0!  Need to check if doesn't exist.
    if not to_imsi or (subscriber.get_account_balance(to_imsi) == None):
        return False, gt("The number you're sending to doesn't exist."
                         " Try again.")
    # Add the pending transfer.
    code = ''
    for _ in range(int(config_db['code_length'])):
        code += str(random.randint(0, 9))
    db = sqlite3.connect(config_db['pending_transfer_db_path'])
    db.execute("INSERT INTO pending_transfers VALUES (?, ?, ?, ?, ?)",
               (code, time.time(), from_imsi, to_imsi, amount))
    db.commit()
    db.close()
    to_num = subscriber.get_numbers_from_imsi(to_imsi)[0]
    amount_str = freeswitch_strings.humanize_credits(amount)
    response = gt("Reply to this message with %(code)s to confirm your"
                  " transfer of %(amount)s to %(to_num)s. Code expires in ten"
                  " minutes.") % {'code': code, 'amount': amount_str,
                                  'to_num': to_num}
    return True, response


def process_confirm(from_imsi, code):
    """Process a confirmation request.

    Args:
      from_imsi: sender's IMSI
      code: the input confirmation code string
    """
    # Step one: delete all the confirm codes older than some time.
    db = sqlite3.connect(config_db['pending_transfer_db_path'])
    db.execute("DELETE FROM pending_transfers"
               " WHERE time - ? > 600", (time.time(),))
    db.commit()

    # Step two: check if this (from_imsi, code) combo is valid.
    r = db.execute("SELECT from_acct, to_acct, amount FROM pending_transfers"
                   " WHERE code=? AND from_acct=?", (code, from_imsi))
    res = r.fetchone()
    if res and len(res) == 3:
        from_imsi, to_imsi, amount = res
        from_num = subscriber.get_numbers_from_imsi(from_imsi)[0]
        to_num = subscriber.get_numbers_from_imsi(to_imsi)[0]
        reason = "SMS transfer from %s to %s" % (from_num, to_num)
        # Deduct credit from the sender.
        from_imsi_old_credit = subscriber.get_account_balance(from_imsi)
        from_imsi_new_credit = int(from_imsi_old_credit) - int(amount)
        events.create_transfer_event(from_imsi, from_imsi_old_credit,
                                     from_imsi_new_credit, reason,
                                     from_number=from_num, to_number=to_num)
        subscriber.subtract_credit(from_imsi, str(int(amount)))
        # Add credit to the recipient.
        to_imsi_old_credit = subscriber.get_account_balance(to_imsi)
        to_imsi_new_credit = int(to_imsi_old_credit) + int(amount)
        events.create_transfer_event(to_imsi, to_imsi_old_credit,
                                     to_imsi_new_credit, reason,
                                     from_number=from_num, to_number=to_num)
        subscriber.add_credit(to_imsi, str(int(amount)))
        # Humanize credit strings
        amount_str = freeswitch_strings.humanize_credits(amount)
        to_balance_str = freeswitch_strings.humanize_credits(
                to_imsi_new_credit)
        from_balance_str = freeswitch_strings.humanize_credits(
                from_imsi_new_credit)
        # Let the recipient know they got credit.
        message = gt("You've received %(amount)s credits from %(from_num)s!"
                     " Your new balance is %(new_balance)s.") % {
                     'amount': amount_str, 'from_num': from_num,
                     'new_balance': to_balance_str}
        sms.send(str(to_num), str(config_db['app_number']), str(message))
        # Remove this particular the transfer as it's no longer pending.
        db.execute("DELETE FROM pending_transfers WHERE code=?"
                   " AND from_acct=?", (code, from_imsi))
        db.commit()
        # Tell the sender that the operation succeeded.
        return True, gt("You've transferred %(amount)s to %(to_num)s. "
                        "Your new balance is %(new_balance)s.") % {
                                'amount': amount_str, 'to_num': to_num,
                                'new_balance': from_balance_str}
    return False, gt("That transfer confirmation code doesn't exist"
                     " or has expired.")


def handle_incoming(from_imsi, request):
    """Called externally by an FS script.

    Args:
      from_imsi: sender's IMSI
      request: a credit transfer or credit transfer confirmation request
    """
    request = request.strip()

    # This parses a to_number (length 1 or more) and an amount that can
    # be formatted using a comma for a thousands seperator and a period for
    # the decimal place
    transfer_command = re.compile(
            r'^(?P<to_number>[0-9]+)'
            r'\*'
            r'(?P<amount>[0-9]*(?:,[0-9]{3})*(?:\.[0-9]*)?)$')
    transfer = transfer_command.match(request)

    confirm_command = re.compile(r'^(?P<confirm_code>[0-9]{%d})$' %
                                 int(config_db['code_length']))
    confirm = confirm_command.match(request)
    _init_pending_transfer_db()
    if transfer:
        to_number, amount = transfer.groups()
        amount = freeswitch_strings.parse_credits(amount).amount_raw
        # Translate everything into IMSIs.
        try:
            to_imsi = subscriber.get_imsi_from_number(to_number)
            _, resp = process_transfer(from_imsi, to_imsi, amount)
        except SubscriberNotFound:
            resp = gt("Invalid phone number: %(number)s" % {'number': to_number})
    elif confirm:
        # The code is the whole request, so no need for groups.
        code = request.strip()
        _, resp = process_confirm(from_imsi, code)
    else:
        # NOTE: Sent when the user tries to transfer credit with the wrong
        #       format message.
        resp = gt("To transfer credit, reply with a message in the"
                            " format 'NUMBER*AMOUNT'.")
    from_number = subscriber.get_numbers_from_imsi(from_imsi)[0]
    sms.send(str(from_number), str(config_db['app_number']), str(resp))
