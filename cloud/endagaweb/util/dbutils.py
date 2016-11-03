"""utlity methods running on the underlying database.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""


def get_db_time(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT statement_timestamp();")
    return cursor.fetchone()[0]
