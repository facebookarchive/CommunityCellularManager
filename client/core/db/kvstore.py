"""A generic key-value store backed by a SQL db.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






from core.db import ConnectorFactory
from core.db.connector import DatabaseError


class KVStore(dict):
    """A simple database-backed dictionary, using a reliable connection
    to that database. Implements standard dict methods as a base class
    for common operations, provides some primitives that subclasses can
    leverage to build more complex operations without having to write
    raw SQL statements.
    """
    def __init__(self, table_name,
                 connector=None,
                 key_name='key', val_name='value', val_type='text'):
        # Passing in a connector argument is intended to be used for testing
        # purposes only (but works more generally).
        self._connector = (connector if connector else
                           ConnectorFactory.get_default_connector())
        self._query_args = {
            "table": table_name,
            "key": key_name,
            "val": val_name,
            "val_type": val_type,
        }
        # table_name == None only used for testing backend connector
        if table_name:
            self._create_templates()
            self.init_table()

    def init_table(self):
        """
        Every instance of this class has an equivalent table schema,
        since they're all just key-value stores.
        """
        self._connector.exec_stmt("CREATE TABLE IF NOT EXISTS "
                                  "%(table)s (id serial PRIMARY KEY, "
                                  "%(key)s text UNIQUE NOT NULL, "
                                  "%(val)s %(val_type)s);" %
                                  self._query_args)

    def _create_templates(self):
        """
        Python DB API doesn't allow parameter substition on the table name,
        so we need a way to insert the table name into each statement we
        want to execute. This is the simplest.
        """
        self._select_item = ("SELECT %(key)s, %(val)s FROM %(table)s;" %
                             self._query_args)
        self._select_value = ("SELECT %(val)s FROM %(table)s "
                              "WHERE %(key)s = %%s;" %
                              self._query_args)
        self._update_item = ("UPDATE %(table)s SET "
                             "%(val)s = %%s WHERE %(key)s = %%s;" %
                             self._query_args)
        self._insert_item = ("INSERT INTO %(table)s "
                             "(%(key)s, %(val)s) VALUES (%%s, %%s);" %
                             self._query_args)
        self._delete_item = ("DELETE FROM %(table)s WHERE %(key)s = %%s" %
                             self._query_args)

    def __getitem__(self, key):
        try:
            val = self._connector.exec_and_fetch_one(self._select_value,
                                                     (key, ))
            return val[0]  # val is a 1-element array
        except (DatabaseError, IndexError):
            raise KeyError(key)

    def __setitem__(self, key, value):
        self._connector.with_cursor(self._set, key, value)

    def __delitem__(self, key):

        self._connector.exec_stmt(self._delete_item, (key, ))

    def __contains__(self, key):

        # SELECT returns empty list if key not found
        return [] != self._connector.exec_and_get_option(self._select_value,
                                                         (key, ))

    def get(self, key, default=None):
        """The dictionary.get paradigm which supports a default value."""
        val = self._connector.with_cursor(self._get_option, key)
        # _get_option returns [] if the key is missing
        return val if val != [] else default

    def items(self):
        return self._connector.exec_and_fetch(self._select_item)

    # some backends (sqlite3) don't support the ANY query function
    _any_supported = True

    def get_multiple(self, keys):
        """ The items corresponding to <keys>. """
        # special cases for 0- and 1-element arrays
        if keys == []:
            return []
        if len(keys) == 1:
            v = self.get(keys[0], [])
            return [(keys[0], v)] if v != [] else []

        if self._any_supported:
            try:
                return self._connector.exec_and_fetch(
                    self._select_item[:-1] +
                    (" WHERE %(key)s = ANY(%%s);" % self._query_args),
                    (keys, ))
            except DatabaseError:
                self.__class__._any_supported = False
        cache = dict(list(self.items()))
        return [(k, cache[k]) for k in keys]

    def substring_search(self, query):
        """Returns a dictionary of keys containing the substring <query>."""
        ret = {}
        try:
            results = self._connector.exec_and_fetch(
                self._select_item[:-1] +
                (" WHERE %(key)s LIKE '%%%%' || %%s || '%%%%';" %
                 self._query_args),
                (query, ))
            for (k, v) in results:
                ret[k] = v
        except (DatabaseError, IndexError):
            pass
        return ret

    def set_multiple(self, data):
        """In one transaction, set multiple values.

        Args:
          data: a list of (key, value) pairs
        """
        def set_multi(cur):
            for key, value in data:
                self._set(cur, key, value)
        self._connector.with_cursor(set_multi)

    # following methods are cursor-based primitives that can be used by db
    # subclasses as parts of a transaction (exec methods each constitute a
    # single transaction, and composing them creates multiple transactions).
    def _get_option(self, cur, key):
        """
        Get a value if it exists in the database. If key is absent return
        the empty array, since None is a valid value that could be stored.

        Raises:
            TypeError if multiple rows were returned.
        """
        cur.execute(self._select_value, (key, ))
        ret = cur.fetchall()
        if len(ret) > 1:
            raise TypeError("multiple rows where one expected")
        # result is a length 1 list with value that is a length 1 list too
        return ret[0][0] if ret != [] else ret

    def _insert(self, cur, key, value):
        self._connector.exec_stmt(self._insert_item, (key, value))

    def _update(self, cur, key, value):
        self._connector.exec_stmt(self._update_item, (value, key))

    def _set(self, cur, key, value):
        # _get_option returns [] if a key doesn't exist since None
        if self._get_option(cur, key) != []:
            self._update(cur, key, value)
        else:
            self._insert(cur, key, value)
