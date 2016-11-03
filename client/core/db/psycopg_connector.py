#!/usr/bin/env python2
# even though this isn't executable code, above line required to prevent
# linting for Python 3

"""Resilient connection to a Postgres DB

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import os

import psycopg2

from .connector import BaseConnector


class PsycopgConnector(BaseConnector):

    db_errors = (psycopg2.Error, psycopg2.Warning)
    db_restart_errors = (psycopg2.InterfaceError, psycopg2.OperationalError)

    # In our CI system, Postgres credentials are stored in env vars.
    def __init__(self,
                 user=os.environ.get('PG_USER', 'endaga'),
                 password=os.environ.get('PG_PASSWORD', 'endaga'),
                 database='endaga',
                 host='localhost'):

        self._database = database
        self._host = host
        self._password = password
        self._user = user
        super(PsycopgConnector, self).__init__()

    def connect(self):

        self._connection = psycopg2.connect(host=self._host,
                                            database=self._database,
                                            user=self._user,
                                            password=self._password)
