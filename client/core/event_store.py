"""
Store system events in the backend database.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import json
import os

import psycopg2

from ccm.common import logger


# In our CI system, Postgres credentials are stored in env vars.
PG_USER = os.environ.get('PG_USER', 'endaga')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'endaga')


class EventStore(object):
    """Keeps track of all system events that need to be sent to the server."""

    def __init__(self):
        self.conn = psycopg2.connect(host='localhost', database='endaga',
                                     user=PG_USER, password=PG_PASSWORD)
        self._createdb()

    def _createdb(self):
        """Creates the main table if it doesn't already exist."""
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS"
                    " endaga_events(seqno bigserial PRIMARY KEY, data json);")
        self.conn.commit()

    def drop_table(self):
        """Drops the main table."""
        cur = self.conn.cursor()
        cur.execute("DROP TABLE IF EXISTS endaga_events;")
        self.conn.commit()

    def set_seqno(self, seqno):
        """Sets the current event seqno to the given value.

        This becomes the CURRENT seqno of the table; the next seqno generated
        will be this value+1.

        We have to grab a *full table lock* on this, otherwise we can have
        issues with writes duplicating the seqno. We should only rarely call
        this -- the only reason the seqno needs to be updated is if we're
        restoring a DB or cloning a BTS.
        """
        cur = self.conn.cursor()
        try:
            cur.execute("LOCK TABLE endaga_events IN EXCLUSIVE MODE;")
            cur.execute("SELECT setval('endaga_events_seqno_seq', %s);",
                        (seqno,))
            self.conn.commit()
        except BaseException:
            logger.error("EventStore: set seqno %s failed" % seqno)
            self.conn.rollback()

    def ack(self, seqno):
        """Process an ack to the db.

        An ack up to a seqno means that all events up to and including that
        seqno have been handled and can be safely removed.
        """
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM endaga_events WHERE seqno<=%s;", (seqno,))
            # If this fails, we don't commit.
            logger.info("EventStore: ack'd seqno %d" % int(seqno))
            self.conn.commit()
        except BaseException as e:
            logger.error("EventStore: ack seqno %s exception %s" % (seqno, e))
            raise

    def add(self, event_dict):
        """Add an event-describing dictionary to the database.

        This method will encode it.
        """
        cur = self.conn.cursor()
        cur.execute("INSERT INTO endaga_events (data) VALUES (%s);",
                    (json.dumps(event_dict),))
        self.conn.commit()

    def get_events(self, num=100):
        """Get the selected number of events from the event store."""
        cur = self.conn.cursor()
        cur.execute("SELECT seqno, data FROM endaga_events"
                    " ORDER BY seqno LIMIT %s;", (num,))
        r = cur.fetchall()
        res = []
        for item in r:
            seqno = item[0]
            d = item[1]
            d['seq'] = seqno
            res.append(d)
        return res

    def modified_subs(self):
        """
        Returns a set of IMSIs that currently have records in the EventStore.

        Note: this relies on Postgres JSON support.
        """
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("SELECT DISTINCT data->>'imsi' AS imsi "
                            "FROM endaga_events;")
                return list(sum(cur.fetchall(), ()))
