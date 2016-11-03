"""Tests for core.number_utilities.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

from core import config_database
from core import number_utilities


class IntlCallingCodeTest(unittest.TestCase):
    """Testing core.number_utilities.calling_code_from_country_code."""

    def test_gb(self):
        expected_calling_code = '44'
        self.assertEqual(expected_calling_code,
                         number_utilities.calling_code_from_country_code('GB'))

    def test_cl(self):
        expected_calling_code = '56'
        self.assertEqual(expected_calling_code,
                         number_utilities.calling_code_from_country_code('CL'))

    def test_usa(self):
        expected_calling_code = '1'
        self.assertEqual(expected_calling_code,
                         number_utilities.calling_code_from_country_code('US'))


class CanonicalizeTest(unittest.TestCase):
    """Test number canonicalization."""
    @classmethod
    def setUpClass(cls):
        cls.config_db = config_database.ConfigDB()

    def test_united_states(self):
        self.config_db['number_country'] = 'US'
        number = '9195551234'
        self.assertEqual('1' + number, number_utilities.canonicalize(number))

    def test_indonesia(self):
        self.config_db['number_country'] = 'ID'
        number = '9195551234'
        self.assertEqual('62' + number, number_utilities.canonicalize(number))

    def test_country_code_already_added(self):
        """If the number already has the country code, we don't add it."""
        self.config_db['number_country'] = 'ID'
        number = '629195551234'
        self.assertEqual(number, number_utilities.canonicalize(number))

    def test_plus(self):
        """Call another country with via the plus sign."""
        # Setup the number_country as ID.
        self.config_db['number_country'] = 'ID'
        # But try to call the US with +1.
        number = '+19195551234'
        self.assertEqual('19195551234', number_utilities.canonicalize(number))

    def test_leading_zero(self):
        """If a number has a leading zero, remove it before canonicalizing."""
        self.config_db['number_country'] = 'ID'
        number = '035551234'
        self.assertEqual('6235551234', number_utilities.canonicalize(number))

    def test_ph_landline(self):
        """PH landline numbers are weird, make sure we
        canonicalize properly. """
        self.config_db['number_country'] = 'PH'
        number = '6323953489'
        self.assertEqual('6323953489', number_utilities.canonicalize(number))
        number = '63023953489'
        self.assertEqual('6323953489', number_utilities.canonicalize(number))
        number = '023953489'
        self.assertEqual('6323953489', number_utilities.canonicalize(number))
