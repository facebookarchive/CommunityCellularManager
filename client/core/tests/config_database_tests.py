"""Tests for the config database.

Usage:
    $ nosetests core.tests.config_database_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






from random import randrange
import unittest

from core.config_database import ConfigDB


class ConfigDBTest(unittest.TestCase):
    """ We can store different types of value into ConfigDB. """

    @classmethod
    def setUpClass(cls):
        cls.config_db = ConfigDB()
        cls.key = 'test-key'

    def tearDown(self):
        """Reset the config db."""
        del self.config_db[self.key]

    def test_boolean(self):
        """We can use booleans."""
        self.config_db['key'] = True
        self.assertEqual(True, self.config_db['key'])

    def test_float(self):
        """We use floats."""
        self.config_db['key'] = 5.2
        self.assertEqual(5.2, self.config_db['key'])

    def test_int(self):
        """ We use integers. """
        val = randrange(0, 1000000)
        self.config_db['key'] = val
        self.assertEqual(val, self.config_db['key'])

    def test_none(self):
        """We use None types."""
        self.config_db['key'] = None
        self.assertEqual(None, self.config_db['key'])
        # verify that we correctly handle the case that the value stored is None
        # and thus we don't want to get the default value from get()
        self.assertEqual(None, self.config_db.get('key', 'foo'))
