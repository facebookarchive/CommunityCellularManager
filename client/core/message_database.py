"""A circular buffer for storing inbound message identifiers.

This is used to avoid processing duplicate inbound messages.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import os

import psycopg2


# In our CI system, Postgres credentials are stored in env vars.
PG_USER = os.environ.get('PG_USER', 'endaga')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'endaga')


class MessageDB(object):
    def __init__(self, max_len=5000):
        self.max_len = max_len
        self.conn = psycopg2.connect(host='localhost', database='endaga',
                                     user=PG_USER, password=PG_PASSWORD)
        self._createdb()

    def __contains__(self, msgid):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT msgid FROM endaga_msgid WHERE msgid=%s;",
                        (msgid,))
            if cur.fetchone() is None:
                return False
            return True
        except (psycopg2.ProgrammingError, IndexError):
            return False

    def _createdb(self):
        cur = self.conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS endaga_msgid(id serial PRIMARY"
                    " KEY, msgid text UNIQUE NOT NULL);")
        self.conn.commit()

    def resize(self, most_recent_id, commit=False):
        """Drops any records with ids at least max_len less than the current
        highest id.
        """
        cur = self.conn.cursor()
        cur.execute("DELETE FROM endaga_msgid WHERE id <= %s;",
                    (most_recent_id - self.max_len,))
        if commit:
            self.conn.commit()

    def seen(self, msgid):
        """Returns True if the msgid has been seen before and False otherwise.

        As a side effect, adds the msgid to the DB if it hasn't been seen
        before and calls resize.
        """
        if self.__contains__(msgid):
            return True
        else:
            cur = self.conn.cursor()
            cur.execute("INSERT INTO endaga_msgid (msgid) VALUES(%s) RETURNING"
                        " id;", (msgid,))
            max_id = int(cur.fetchone()[0])
            self.resize(max_id)
            self.conn.commit()
            return False
