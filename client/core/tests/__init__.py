"""
Initialise ConfigDB so that it can be used for testing without Postgres.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






from logging import StreamHandler
from os import environ
from sys import stdout

from ccm.common.logger import DefaultLogger
from core.db import ConnectorFactory

# Make all instances of KVStore connect to a shared sqlite3 backend, unless
# we explicitly ask for Postgres. Must do before importing config_database.
if environ.get('CCM_DB_TEST_BACKEND') == 'postgres':
    from core.db.psycopg_connector import PsycopgConnector
    ConnectorFactory.set_default_connector(PsycopgConnector())
else:
    from .sqlite3_connector import Sqlite3Connector
    ConnectorFactory.set_default_connector(Sqlite3Connector())

from core.config_database import ConfigDB, set_defaults

# initialise default config, since various imports read config
set_defaults()
_conf = ConfigDB()
_conf['bts.type'] = 'fake'


# set default logger to stdout so that output gets swalled by nose/Buck
DefaultLogger.update_handler(StreamHandler(stdout))
