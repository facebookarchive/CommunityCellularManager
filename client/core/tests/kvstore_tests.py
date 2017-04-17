"""Tests for the KVStore class.

Usage:
    $ nosetests core.tests.kvstore_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






from os import environ
from random import randrange

import unittest

from core.db.connector import ConnectorAbort
from core.db.kvstore import KVStore
from .sqlite3_connector import Sqlite3Connector


class StubDatabase(KVStore):

    def __init__(self, connector=None, table_name='test_db', val_type='text'):
        self._val_type = val_type
        super(StubDatabase, self).__init__(
            table_name, connector, val_type=val_type)


# create derived classes to test connection sharing
class StubDBOne(StubDatabase):
    """Connector inherited from and shared with StubDatabase."""
    def __init__(self):
        super(StubDBOne, self).__init__(None, None)


class StubDBTwo(StubDatabase):
    """Connector not shared with StubDatabase."""
    _shared_connector = None

    def __init__(self):
        super(StubDBTwo, self).__init__(self._shared_connector, None)


class ConnectorTest(unittest.TestCase):
    """ Test sharing (and non-sharing) of connectors by db instances."""

    @classmethod
    def setUpClass(cls):
        cls.db = StubDatabase(table_name=None)

    def test_shared_connector(self):
        """Multiple instances of ConfigDB share a single db connector."""
        db = StubDatabase(table_name=None)
        self.assertEqual(db._connector, self.db._connector)

    def test_private_connector(self):
        """Database can be instantiated with a different connector."""
        db = StubDatabase(Sqlite3Connector(), table_name=None)
        self.assertNotEqual(db._connector, self.db._connector)

    def test_subclass_shared_connector(self):
        """ Subclasses get the default connector. """
        db = StubDBOne()
        self.assertEqual(db._connector, self.db._connector)

    def test_subclass_private_connector(self):
        """Subclasses can have their own shared connector."""
        StubDBTwo._shared_connector = Sqlite3Connector()
        db_x = StubDBTwo()
        db_y = StubDBTwo()
        self.assertEqual(db_x._connector, db_y._connector)
        self.assertNotEqual(db_x._connector, self.db._connector)


class KVStoreTest(unittest.TestCase):
    """We can use the KVStore methods."""

    @classmethod
    def setUpClass(cls):
        cls.db = StubDatabase()

    def test_insert(self):
        """We can insert data."""
        self.db['test-key'] = 'test-val'
        self.assertEqual('test-val', self.db['test-key'])

    def test_update(self):
        """We can update data."""
        del self.db['test-key']
        self.db['test-key'] = None  # check we can insert None
        self.db['test-key'] = 'test-val'
        self.db['test-key'] = None  # check we can update value to None
        self.db['test-key'] = 'new-val'
        self.assertEqual('new-val', self.db['test-key'])

    def test_contains(self):
        """We can check if a key is present."""
        key = 'key-%d' % (randrange(0, 1e9), )
        self.assertFalse(key in self.db)
        self.db[key] = 'yup'
        self.assertTrue(key in self.db)
        del self.db[key]

    def test_delete(self):
        """We can delete data."""
        self.db['test-key'] = 'test-val'
        del self.db['test-key']
        self.assertFalse('test-key' in self.db)

    def test_set_multiple(self):
        """We can set multiple values at once."""
        data = [
            ('key-1', 'foo'),
            ('key-2', 'bar'),
            ('key-3', 'baz'),
        ]
        self.db.set_multiple(data)
        for item in data:
            self.assertEqual(item[1], self.db[item[0]])
            del self.db[item[0]]

    def test_get(self):
        """We can get with a default value."""
        self.db['test-key'] = 'yup!'
        self.assertEqual('yup!', self.db.get('test-key', None))
        self.assertEqual('nope', self.db.get('bad-key', 'nope'))

    def test_get_multiple(self):
        """ We can get a subset of items with specified keys. """
        data = {
            'key0': 'foo',
            'key1': 'bar',
            'key2': 'baz',
        }
        self.db.set_multiple(list(data.items()))
        del data['key1']
        res = self.db.get_multiple(['key0', 'key2'])
        self.assertEqual(2, len(res))
        for (k, v) in res:
            self.assertEqual(data[k], v)
            del self.db[k]

    def test_get_multiple_zero(self):
        """ We can get a subset (size 0) of items with specified keys. """
        data = {
            'key0': 'foo',
            'key1': 'bar',
            'key2': 'baz',
        }
        self.db.set_multiple(list(data.items()))
        self.assertEqual([], self.db.get_multiple([]))

    def test_get_multiple_one(self):
        """ We can get a subset (size 1) of items with specified keys. """
        data = {
            'key0': 'foo',
            'key1': 'bar',
            'key2': 'baz',
        }
        self.db.set_multiple(list(data.items()))
        self.assertEqual([('key0', 'foo')], self.db.get_multiple(['key0']))

    def test_items(self):
        """ We can get all items in the db. """
        # clear db first
        for (k, _) in list(self.db.items()):
            del self.db[k]
        data = {
            'key0': 'foo',
            'key1': 'bar',
            'key2': 'baz',
        }
        self.db.set_multiple(list(data.items()))
        res = list(self.db.items())
        self.assertEqual(len(data), len(res))
        for (k, v) in res:
            self.assertEqual(data[k], v)
            del self.db[k]

    def test_substring_search(self):
        """We can search for multiple configs that match a query."""
        data = {
            'key-a': 'foo',
            'key-aa-': 'bar',
            'key-aaa--': 'baz',
        }
        self.db.set_multiple(list(data.items()))
        res = self.db.substring_search('aa')
        self.assertEqual(2, len(res))
        for (k, v) in list(res.items()):
            self.assertEqual(data[k], v)
            del self.db[k]


class TransactionTest(unittest.TestCase):
    """
    Test that transactions work the way they are supposed to.
    Python DB API uses connections to manage transactions, not cursors.
    A connection object can be used directly as a context manager to
    indicate the start and end of a transaction; successful execution
    (no exceptions raised) of the associated block commits the transaction,
    otherwise it's aborted.

    One consequence of transactions not being associated with cursors:
    'nested' transactions don't behave as expected:
     * Rolling back an 'inner txn' (cursor) does nothing - any updates made
       by that cursor will still be visible in the outer txn, and committed
       if the outer is committed.
     * Committing the inner txn is NOT reverted if the outer txn is rolled
       back. Since transactions are not bound to cursors, commit() applies
       to the connection-level transaction, and a new transaction begins
       once the outer txn executes another statement.
    """

    @classmethod
    def setUpClass(cls):
        # set the shared connector
        cls.db = StubDatabase(table_name='txn_test_db', val_type='INTEGER')

    # Cursors DO NOT map to transactions, which is (perhaps) not intuitive.
    # These tests mostly just illustrate how they behave, but also confirm
    # that we are using them correctly.
    def test_nested_cursor(self):
        """ We can use one cursor context inside another such context."""
        def inner(cur, v1_expected):
            v1 = self.db._get_option(cur, 'key-1')
            # value set in outer context should be visible
            self.assertEqual(v1, v1_expected)
            # update value
            delta = randrange(1e7, 2e7)
            self.db._set(cur, 'key-1', v1 + delta)
            return delta

        def outer(cur):
            v1 = randrange(0, 1e6)
            self.db._set(cur, 'key-1', v1)
            delta = self.db._connector.with_cursor(inner, v1)
            # change made in inner context should be visible
            self.assertEqual(v1 + delta, self.db._get_option(cur, 'key-1'))

        self.db._connector.with_cursor(outer)

    def test_interleaved_cursor(self):
        """ We can use one cursor context interleaved with another context."""
        def inner(cur, outer_cur, v1_expected):
            v1 = self.db._get_option(cur, 'key-1')
            # value set in outer context should be visible
            self.assertEqual(v1, v1_expected)
            # update value using outer cursor
            delta = randrange(1e7, 2e7)
            self.db._set(outer_cur, 'key-1', v1 + delta)
            return delta

        def outer(cur):
            v1 = randrange(0, 1e6)
            self.db._set(cur, 'key-1', v1)
            delta = self.db._connector.with_cursor(inner, cur, v1)
            # change made in inner context should be visible
            self.assertEqual(v1 + delta, self.db._get_option(cur, 'key-1'))

        self.db._connector.with_cursor(outer)

    def test_nested_txn(self):
        """ We can nest one transaction within another."""
        def inner(conn, v1_expected):
            with conn:
                cur = conn.cursor()
                v1 = self.db._get_option(cur, 'key-1')
                # value set in outer txn should be visible
                self.assertEqual(v1, v1_expected)
                # update value
                delta = randrange(1e7, 2e7)
                self.db._set(cur, 'key-1', v1 + delta)
                return delta

        def outer(cur):
            v1 = randrange(0, 1e6)
            self.db._set(cur, 'key-1', v1)
            delta = self.db._connector.execute(inner, v1)
            # change made in inner context should be visible
            self.assertEqual(v1 + delta, self.db._get_option(cur, 'key-1'))

        self.db._connector.with_cursor(outer)

    def test_nested_txn_abort(self):
        """ Aborting a nested transaction does not roll back updates."""
        def inner(conn, v1_expected, delta):
            with conn:
                cur = conn.cursor()
                v1 = self.db._get_option(cur, 'key-1')
                # value set in outer txn should be visible
                self.assertEqual(v1, v1_expected)
                # update value
                self.db._set(cur, 'key-1', v1 + delta)
                # this update should be rolled back
                raise ConnectorAbort("testing rollback")

        def outer(cur):
            v1 = randrange(0, 1e6)
            self.db._set(cur, 'key-1', v1)
            delta = randrange(1e7, 2e7)
            self.db._connector.execute(inner, v1, delta)
            # change made in inner context are NOT rolled back
            self.assertEqual(v1 + delta, self.db._get_option(cur, 'key-1'))

        self.db._connector.with_cursor(outer)

    def test_interleaved_txn_abort(self):
        """ Transactions are managed at the connection level."""
        def inner(conn, outer_cur, v1_expected, delta):
            with conn:
                cur = conn.cursor()
                v1 = self.db._get_option(cur, 'key-1')
                # value set in outer txn should be visible
                self.assertEqual(v1, v1_expected)
                # update value using outer cursor
                # can use outer cursor in inner transaction
                self.db._set(outer_cur, 'key-1', v1 + delta)
                raise ConnectorAbort("testing rollback")

        def outer(cur):
            v1 = randrange(0, 1e6)
            self.db._set(cur, 'key-1', v1)
            delta = randrange(1e7, 2e7)
            self.db._connector.execute(inner, cur, v1, delta)
            # change made in inner context should NOT have been rolled back
            self.assertEqual(v1 + delta, self.db._get_option(cur, 'key-1'))
            return v1 + delta

        # set an initial value
        v0 = randrange(0, 1e5)
        self.db['key-1'] = v0
        v2 = self.db._connector.with_cursor(outer)
        # check that inner connection was not rolled back
        self.assertEqual(v2, self.db['key-1'])

    def test_inner_commit(self):
        """We can commit a nested transaction."""
        def inner(conn, v1_expected, delta):
            with conn:
                cur = conn.cursor()
                v1 = self.db._get_option(cur, 'key-1')
                # value set in outer txn should be visible
                self.assertEqual(v1, v1_expected)
                # update value
                self.db._set(cur, 'key-1', v1 + delta)
                return delta

        def outer(cur, v1, delta):
            self.db._set(cur, 'key-1', v1)
            self.db._connector.execute(inner, v1, delta)
            # change made in inner context were committed
            self.assertEqual(v1 + delta, self.db._get_option(cur, 'key-1'))
            raise ConnectorAbort("testing outer rollback")

        # set an initial value
        v0 = randrange(0, 1e5)
        self.db['key-1'] = v0
        v1 = randrange(v0, 1e6)
        v1_delta = randrange(1e7, 2e7)
        self.db._connector.with_cursor(outer, v1, v1_delta)
        # test that inner txn changes have not been rolled back
        self.assertEqual(v1 + v1_delta, self.db['key-1'])
