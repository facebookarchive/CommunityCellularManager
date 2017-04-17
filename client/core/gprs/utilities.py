"""GPRS utils for gathering usage data and generating events.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import humanize

from core import events
from core.gprs import gprs_database
from core.subscriber import subscriber
from core.exceptions import SubscriberNotFound


def gather_gprs_data():
    """Gets GPRS data from openbts-python and dumps it in the GPRS DB."""
    gprs_db = gprs_database.GPRSDB()
    try:
        data = subscriber.get_gprs_usage()
    except SubscriberNotFound:
        return
    for imsi in list(data.keys()):
        # If the IMSI is not a registered sub, ignore its data.
        if not subscriber.get_subscribers(imsi=imsi):
            continue
        # Otherwise, get the IMSI's latest record and compute the byte count
        # deltas.
        record = gprs_db.get_latest_record(imsi)
        if not record:
            # No previous records exist for this IMSI so set the old byte
            # counts to zero.
            old_up_bytes = 0
            old_down_bytes = 0
        elif record['ipaddr'] != data[imsi]['ipaddr']:
            # The ipaddr has been reset and with it, the byte count.
            old_up_bytes = 0
            old_down_bytes = 0
        elif (record['uploaded_bytes'] > data[imsi]['uploaded_bytes'] or
              record['downloaded_bytes'] > data[imsi]['downloaded_bytes']):
            # The ipaddr was recently re-assigned to this IMSI and it happens
            # to match the IP we had previously.  The byte count was reset
            # during this transition.
            old_up_bytes = 0
            old_down_bytes = 0
        else:
            old_up_bytes = record['uploaded_bytes']
            old_down_bytes = record['downloaded_bytes']
        up_bytes_delta = data[imsi]['uploaded_bytes'] - old_up_bytes
        down_bytes_delta = data[imsi]['downloaded_bytes'] - old_down_bytes
        # Insert the GPRS data into the DB.
        gprs_db.add_record(
            imsi, data[imsi]['ipaddr'], data[imsi]['uploaded_bytes'],
            data[imsi]['downloaded_bytes'], up_bytes_delta, down_bytes_delta)


def generate_gprs_events(start_timestamp, end_timestamp):
    """Create GPRS events from data in the GPRS DB.

    Records that were generated between the specified timestamp will become
    events.  One event is created per IMSI (not one event per record).

    Args:
      start_timestamp: seconds since epoch
      end_timestamp: seconds since epoch
    """
    gprs_db = gprs_database.GPRSDB()
    # First organize the records by IMSI.
    sorted_records = {}
    for record in gprs_db.get_records(start_timestamp, end_timestamp):
        if record['imsi'] not in sorted_records:
            sorted_records[record['imsi']] = []
        sorted_records[record['imsi']].append(record)
    # Now analyze all records that we have for each IMSI.
    for imsi in sorted_records:
        up_bytes = sum(
            [r['uploaded_bytes_delta'] for r in sorted_records[imsi]])
        down_bytes = sum(
            [r['downloaded_bytes_delta'] for r in sorted_records[imsi]])
        # Do not make an event if the byte deltas are unchanged.
        if up_bytes == 0 and down_bytes == 0:
            continue
        # For now, GPRS is free for subscribers.
        cost = 0
        reason = 'gprs_usage: %s uploaded, %s downloaded' % (
            humanize.naturalsize(up_bytes), humanize.naturalsize(down_bytes))
        timespan = int(end_timestamp - start_timestamp)
        events.create_gprs_event(
            imsi, cost, reason, up_bytes, down_bytes, timespan)


def clean_old_gprs_records(timestamp):
    """Remove records from the GPRS DB that are older than timestamp.

    We just do this to prevent the table from growing without bound.  And we
    don't delete GPRS records immediately after their conversion to events in
    case we want them for analysis later.

    Args:
      timestamp: seconds since epoch
    """
    gprs_db = gprs_database.GPRSDB()
    gprs_db.delete_records(timestamp)
