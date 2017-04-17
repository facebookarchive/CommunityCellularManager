"""Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

# Tests for the database connector.
#
# Usage:
#     nosetests core.tests.db_connector_tests






from random import randrange
import sqlite3
import unittest

from core.db.connector import ConnectorAbort, ConnectorError, DatabaseError
from .sqlite3_connector import RestartError, Sqlite3Connector


class DbConnectorTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.connector = Sqlite3Connector()
        cls.connector.with_cursor(
            lambda cur: cur.execute(
                "CREATE TABLE IF NOT EXISTS "
                "connector_test(id serial PRIMARY KEY, "
                "key text UNIQUE NOT NULL, "
                "value INTEGER);"))

    @classmethod
    def get_val(cls, key):
        try:
            return cls.connector.exec_and_fetch_one(
                "SELECT value FROM connector_test WHERE key=?;",
                (key, ))[0]
        except IndexError:
            raise KeyError

    @staticmethod
    def _set(cur, key, val):
        cur.execute("SELECT value FROM connector_test WHERE key=?;",
                    (key, ))
        if cur.fetchone():
            cur.execute("UPDATE connector_test SET value=? WHERE"
                        " key=?;", (val, key))
        else:
            cur.execute("INSERT INTO connector_test (key, value) VALUES"
                        " (?, ?);", (key, val))

    @classmethod
    def set_val(cls, key, val):
        return cls.connector.with_cursor(cls._set, key, val)

    @classmethod
    def _insert_new(cls, key):

        new_val = randrange(0, 1000000)
        cls.set_val(key, new_val)
        return new_val

    def _test_until(self, cur, test_data, n):
        """
        This is the worker function used by each test. It attempts to make
        a database update using key and value from test_data[i] on the
        i'th iteration of the transaction. Each iterator prior to the value
        i == self._test_n is aborted by restarting the connector.
        """
        (k, v) = test_data[self._test_i]
        self._set(cur, k, v)
        if self._test_i < n:
                self._test_i += 1
                raise RestartError()

    def _run_test(self, data, n=1000):
        self._test_i = 0
        self.connector.with_cursor(self._test_until, data, n)

    def test_abort(self):
        """ We can explicitly abort a transaction. """
        prior = randrange(0, 1000000)
        self.set_val('key0', prior)
        self.assertEqual(prior, self.get_val('key0'))

        def _abort(cur, delta):
            self._set(cur, 'key0', prior + delta)
            raise ConnectorAbort

        self.connector.with_cursor(_abort, randrange(1, 1e6))
        self.assertEqual(prior, self.get_val('key0'))

    def test_restart(self):
        """We can restart a transaction."""
        test_data = [('key0', randrange(0, 1000000)),
                     ('key0', randrange(0, 1000000))]

        self._run_test(test_data, 1)
        self.assertEqual(test_data[1][1], self.get_val('key0'))

    def test_restart_twice(self):
        """We can restart a transaction twice."""
        test_data = [('key0', randrange(0, 1000000)),
                     ('key0', randrange(0, 1000000)),
                     ('key0', randrange(0, 1000000))]

        self._run_test(test_data, 2)
        self.assertEqual(test_data[2][1], self.get_val('key0'))

    def test_restart_limit(self):
        """There is a limit (2) to how many times we restart a transaction."""
        test_data = [('key0', randrange(0, 1000000)),
                     ('key0', randrange(0, 1000000)),
                     ('key0', randrange(0, 1000000)),
                     ('key0', randrange(0, 1000000))]
        # insert a value that we want to confirm is not overwritten
        val0 = self._insert_new('key0')

        # verify that restarting a transaction too often raises an Error
        with self.assertRaises(ConnectorError):
            self._run_test(test_data)
        # verify that no update was committed
        self.assertEqual(val0, self.get_val('key0'))

    def test_rollback(self):
        """We can rollback a transaction."""
        test_data = [('key0', randrange(0, 1000000)),
                     ('key1', randrange(0, 1000000))]
        # insert a value that we want to confirm is not overwritten
        val0 = self._insert_new('key0')

        self._run_test(test_data, 1)
        # verify that change to key0 was rolled back
        self.assertEqual(val0, self.get_val('key0'))
        # verify that change to key1 was committed
        self.assertEqual(test_data[1][1], self.get_val('key1'))

    def test_db_error(self):
        """A db error gets wrapped in DatabaseError."""

        def tester(cur):
            raise sqlite3.Error()
        with self.assertRaises(DatabaseError):
            self.connector.with_cursor(tester)
