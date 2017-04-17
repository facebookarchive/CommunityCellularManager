"""Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import re
import sqlite3

from core.db.connector import BaseConnector


# exception used to simulate db restart during testing
class RestartError(sqlite3.Error):
    """
    Subclass of sqlite3.Error so that we can verify that restart errors
    are handled correctly as separate from other errors that are derived
    from the database's base error class.
    """
    pass


class Sqlite3Connection(sqlite3.Connection):
    """
    Wrap the sqlite3 Connection class so that cursors are always created
    using the subclass below, which ensures translation of format specifiers
    in SQL statements to the sqlite3 style.
    """
    def cursor(self, factory=None):
        """
        There isn't an easy way to add the translation function to arbitrary
        cursor subclasses created via the factory argument.
        """
        if factory:
            raise ValueError("cursor factories not currently supported")
        return Sqlite3Cursor(self)


class Sqlite3Connector(BaseConnector):

    db_restart_errors = (RestartError, )
    db_errors = (sqlite3.Error, )

    def __init__(self):
        # reuse a single sqlite3 in-memory instance across simulated restarts
        self._backend = sqlite3.connect(':memory:', factory=Sqlite3Connection)
        # set the max number of connection retry attempts to two
        super(Sqlite3Connector, self).__init__(2)

    def connect(self):
        self._connection = self._backend


class Sqlite3Cursor(sqlite3.Cursor):
    """
    sqlite3 uses simple '?' positional specifiers for param substitution
    rather than '%s' style specifiers used by psycopg2. We need to wrap
    the execute() method (and all related methods) to transform any
    '%s' (or similar) specifiers appropriately.
    """
    def __init__(self, conn):
        super(Sqlite3Cursor, self).__init__(conn)

    # define __enter__ and __exit__ methods so that we can use cursors
    # as context managers, even though base sqlite3 cursors cannot
    def __enter__(self):
        # must return the value passed to Y in 'with X as Y'
        return self

    def __exit__(self, ex_type, ex_val, ex_tb):
        # return False to prevent exception suppression
        return False

    def execute(self, stmt, *args):
        if args:
            # no args => don't do substitution
            stmt = self.xform_stmt(stmt)
        super(Sqlite3Cursor, self).execute(stmt, *args)

    def executemany(self, stmt, args):
        super(Sqlite3Cursor, self).executemany(self.xform_stmt(stmt), args)

    # use of a param substitution specifier not listed in this map will
    # result in a KeyError
    _format_spec_map = {
        's': '?',
        '%': '%',  # first '%' symbol automatically stripped
    }
    _format_spec_re = re.compile('%(.)')

    @classmethod
    def xform_stmt(cls, stmt):
        return cls._format_spec_re.sub(
            lambda m: cls._format_spec_map[m.group(1)], stmt)
