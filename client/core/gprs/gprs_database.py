"""Storing GPRS-related data.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import os
import time

import psycopg2


# In our CI system, Postgres credentials are stored in env vars.
PG_USER = os.environ.get('PG_USER', 'endaga')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'endaga')


class GPRSDB(object):
    """Manages connections to the GPRS DB.

    Convention is to close all cursors after opening and immediately commit
    transactions, even if the query is just a 'select.'
    """
    def __init__(self):
        self.connection = psycopg2.connect(host='localhost', database='endaga',
                                           user=PG_USER, password=PG_PASSWORD)
        self.table_name = 'gprs_records'
        # Create the table if it doesn't yet exist.
        with self.connection.cursor() as cursor:
            command = ("CREATE TABLE IF NOT EXISTS %s("
                       " id serial PRIMARY KEY,"
                       " record_timestamp timestamp default current_timestamp,"
                       " imsi text,"
                       " ipaddr text,"
                       " uploaded_bytes integer,"
                       " downloaded_bytes integer,"
                       " uploaded_bytes_delta integer,"
                       " downloaded_bytes_delta integer"
                       ");")
            cursor.execute(command % self.table_name)
            self.connection.commit()

    def empty(self):
        """Drops all records from the table."""
        with self.connection.cursor() as cursor:
            command = 'truncate %s' % self.table_name
            cursor.execute(command)
            self.connection.commit()

    def add_record(self, imsi, ipaddr, up_bytes, down_bytes, up_bytes_delta,
                   down_bytes_delta):
        """Adds a record into the GPRS DB.

        See the schema definition in __init__ for type information.  Record is
        automatically added with record_timestamp set to the current time.
        """
        schema = ('imsi, ipaddr, uploaded_bytes, downloaded_bytes,'
                  ' uploaded_bytes_delta, downloaded_bytes_delta')
        values = "'%s', '%s', %s, %s, %s, %s" % (
            imsi, ipaddr, up_bytes, down_bytes, up_bytes_delta,
            down_bytes_delta)
        command = 'insert into %s (%s) values(%s)' % (
            self.table_name, schema, values)
        with self.connection.cursor() as cursor:
            cursor.execute(command)
            self.connection.commit()

    def get_latest_record(self, imsi):
        """Gets the most recent record for an IMSI.

        Returns None if no record was found.
        """
        command = "select * from %s where imsi='%s' order by id desc limit 1"
        with self.connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(command % (self.table_name, imsi))
            self.connection.commit()
            if not cursor.rowcount:
                return None
            else:
                return cursor.fetchall()[0]

    def get_records(self, start_timestamp=0, end_timestamp=None):
        """Gets records from the table between the specified timestamps.

        Args:
          Timestamps are given in seconds since epoch.

        Returns a list of dicts, each of the form: {
            'id': 3,
            'record_timestamp': 1341556432,
            'imsi': 'IMSI901550000000084',
            'ipaddr': '192.168.99.3',
            'uploaded_bytes': 5567,
            'downloaded_bytes': 9987,
            'uploaded_bytes_delta': 74,
            'downloaded_bytes_delta': 139
        }
        """
        start = psycopg2.TimestampFromTicks(start_timestamp)
        if not end_timestamp:
            end_timestamp = time.time()
        end = psycopg2.TimestampFromTicks(end_timestamp)
        template = ('select * from %s where record_timestamp >= %s'
                    ' and record_timestamp <= %s')
        command = template % (self.table_name, start, end)
        with self.connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(command)
            self.connection.commit()
            return cursor.fetchall()

    def delete_records(self, timestamp):
        """Deletes records older than the given epoch timestamp."""
        timestamp = psycopg2.TimestampFromTicks(timestamp)
        template = 'delete from %s where record_timestamp < %s'
        command = template % (self.table_name, timestamp)
        with self.connection.cursor() as cursor:
            cursor.execute(command)
            self.connection.commit()
