"""
Common database-related stuff

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""







# Factory is here rather than connectory module so that we don't have
# circular dependency between base class and db-specific modules.
#
# It's okay to use this stuff in an environment where psycopg2 is not
# available, since we don't want to depend upon Postgres for testing.
try:
    from .psycopg_connector import PsycopgConnector
except ImportError:
    class PsycopgConnector(object):
        def __init__(self):
            raise RuntimeError("Postgres/psycopg2 not available")


class ConnectorFactory(object):
    """
    Create a singleton database connector to be used wherever connection
    to backend db is needed.
    """
    _default_connector = None

    @classmethod
    def get_default_connector(cls):
        """ Return a reference to the shared instance of the db connector. """
        if not cls._default_connector:
            cls._default_connector = PsycopgConnector()
        return cls._default_connector

    @classmethod
    def set_default_connector(cls, connector):
        cls._default_connector = connector
