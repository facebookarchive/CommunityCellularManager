"""This provides an API for obtaining system status information.

Each method returns a dictionary containing various key-value pairs relating to
status. Note that values can be dictionaries or lists themselves.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import time

from ccm.common import logger
from core.event_store import EventStore
from core.subscriber import subscriber


def usage(num=100):
    """Returns 'events': List of credits log entries."""
    es = EventStore()
    events = es.get_events(num)
    return {'events': events}


def kind_from_reason(reason_str):
    types = ["local_call", "local_sms", "outside_call", "outside_sms",
             "free_call", "free_sms", "incoming_sms", "error_sms",
             "error_call", "transfer", "add_money", "deduct_money",
             "set_balance", "unknown", "Provisioned", "local_recv_call",
             "local_recv_sms", "incoming_call", "gprs"]
    for t in types:
        if t in reason_str:
            return t
    return "unknown"


def create_transfer_event(imsi, old_credit, new_credit, reason,
                          from_number=None, to_number=None):
    """Creates a credit transfer event."""
    _create_event(imsi, old_credit, new_credit, reason,
                  from_number=from_number, to_number=to_number)


def create_add_money_event(imsi, old_credit, new_credit, reason, to_number=None):
    """Creates an event noting that the web UI added credit to this sub.

    TODO(matt): should maybe just add this event on the web-side.
    """
    _create_event(imsi, old_credit, new_credit, reason, to_number=to_number)


def create_provision_event(imsi, reason):
    """Creates an event noting that the specified IMSI was provisioned."""
    old_credit, new_credit = 0, 0
    _create_event(imsi, old_credit, new_credit, reason)


def create_call_event(owner_imsi, from_imsi, from_number, to_imsi, to_number,
                      old_balance, cost, kind, reason, tariff, call_duration,
                      billsec):
    """Creates a call event with data attached to the owner_imsi.

    This event can be created for outgoing and incoming calls.  For the former,
    the event data will be attached to the from_imsi.  For incoming calls,
    the owner_imsi will be the to_imsi.
    """
    new_balance = old_balance - int(cost)
    # Clamp the new_balance to a min of zero.
    if new_balance < 0:
        message = 'Nearly created a call event with a negative new_balance'
        message += ' for %s.  Old balance: %s, cost: %s, reason: %s' % (
            owner_imsi, old_balance, cost, reason)
        logger.warning(message)
        new_balance = 0
    _create_event(owner_imsi, old_balance, new_balance, reason, kind=kind,
                  call_duration=call_duration, billsec=billsec,
                  from_imsi=from_imsi, from_number=from_number,
                  to_imsi=to_imsi, to_number=to_number, tariff=tariff)


def create_sms_event(owner_imsi, old_balance, cost, reason, to_number,
                     from_imsi=None, from_number=None):
    """Creates an SMS-related event with data attached to the owner_imsi."""
    new_balance = old_balance - int(cost)
    # Clamp the new_balance to a min of zero.
    if new_balance < 0:
        message = 'Nearly created an sms event with a negative new_balance'
        message += ' for %s.  Old balance: %s, cost: %s, reason: %s' % (
            owner_imsi, old_balance, cost, reason)
        logger.warning(message)
        new_balance = 0
    _create_event(owner_imsi, old_balance, new_balance, reason,
                  from_imsi=from_imsi, from_number=from_number,
                  to_number=to_number, tariff=cost)


def create_gprs_event(imsi, cost, reason, up_bytes, down_bytes, timespan):
    """Creates a GPRS event.

    Args:
      up_bytes: integer amount of data uploaded during the timespan
      down_bytes: integer amount of data downloaded during the timespan
      timsespan: number of seconds over which this measurement was taken
    """
    old_balance = int(subscriber.get_account_balance(imsi))
    new_balance = max(0, old_balance - int(cost))
    _create_event(imsi, old_balance, new_balance, reason, up_bytes=up_bytes,
                  down_bytes=down_bytes, timespan=timespan)


def _create_event(imsi, old_credit, new_credit, reason, kind=None,
                  call_duration=None, billsec=None, from_imsi=None,
                  from_number=None, to_imsi=None, to_number=None, tariff=None,
                  up_bytes=None, down_bytes=None, timespan=None, write=True):
    """Logs a generic UsageEvent in the EventStore.

    Also writes this action to logger.

    Args:
      imsi: the IMSI connected to this event
      old_credit: the account's balance before this action
      new_credit: the account's balance after this action
      reason: a string describing this event
      kind: the type of event.  If None, we will attempt to lookup the type
            based on the reason.
      call_duration: duration, including connect, if it was a call (seconds)
      billsec: billable duration of the event if it was a call (seconds)
      from_imsi: sender IMSI
      from_number: sender number
      to_imsi: destination IMSI
      to_number: destination number
      tariff: the cost per unit applied during this transaction
      up_bytes: integer amount of data uploaded during the timespan
      down_bytes: integer amount of data downloaded during the timespan
      timsespan: number of seconds over which this measurement was taken
      write: write event to the eventstore (default: True; only for tests)

    Returns:
        A dictionary representing the event
    """
    template = ('new event: user: %s, old_credit: %d, new_credit: %d,'
                ' change: %d, reason: %s\n')
    message = template % (imsi, old_credit, new_credit, new_credit-old_credit,
                          reason)
    logger.info(message)
    # Add this event to the DB.  This is the canonical definition of a
    # UsageEvent.
    # Version 5: added up_bytes, down_bytes and timespan
    # Version 4: added billsec, call_duration (removed underscore)
    # Version 3: ~~a mystery~~
    # Version 2: added 'call duration', from_imsi, to_imsi, from_number,
    #            to_number
    # Version 1: date, imsi, oldamt, newamt, change, reason, kind
    if not kind:
        kind = kind_from_reason(reason)
    data = {
        'date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'imsi': imsi,
        'oldamt': old_credit,
        'newamt': new_credit,
        'change': new_credit - old_credit,
        'reason': reason,
        'kind': kind,
        'call_duration': call_duration,
        'billsec': billsec,
        'from_imsi': from_imsi,
        'to_imsi': to_imsi,
        'from_number': from_number,
        'to_number': to_number,
        'tariff': tariff,
        'up_bytes': up_bytes,
        'down_bytes': down_bytes,
        'timespan': timespan,
        'version': 5,
    }

    # TODO(shasan): find a way to remove this and mock out in testing instead
    if write:
        event_store = EventStore()
        event_store.add(data)
    return data
