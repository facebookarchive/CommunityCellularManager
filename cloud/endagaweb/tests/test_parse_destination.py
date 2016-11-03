"""Testing the ability to detect a phone number's corresponding Destination.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

from endagaweb import models
from endagaweb.util.parse_destination import parse_destination


class DestinationTest(unittest.TestCase):
    """Testing util.parse_destination.parse_destination."""

    @classmethod
    def setUpClass(cls):
        """Create some Destinations for the test."""
        cls.destination_one = models.Destination(prefix='1')
        cls.destination_one.save()
        cls.destination_two = models.Destination(prefix='12')
        cls.destination_two.save()
        cls.destination_three = models.Destination(prefix='123')
        cls.destination_three.save()
        cls.destination_four = models.Destination(prefix='567')
        cls.destination_four.save()
        cls.destinations = [cls.destination_one, cls.destination_two,
                            cls.destination_three, cls.destination_four]

    @classmethod
    def tearDownClass(cls):
        cls.destination_one.delete()
        cls.destination_two.delete()
        cls.destination_three.delete()
        cls.destination_four.delete()

    def test_one(self):
        phone_number = '11235551234'
        expected = self.destination_one
        actual = parse_destination(phone_number, self.destinations)
        self.assertEqual(expected, actual)

    def test_two(self):
        phone_number = '121235551234'
        expected = self.destination_two
        actual = parse_destination(phone_number, self.destinations)
        self.assertEqual(expected, actual)

    def test_three(self):
        phone_number = '1231235551234'
        expected = self.destination_three
        actual = parse_destination(phone_number, self.destinations)
        self.assertEqual(expected, actual)

    def test_four(self):
        phone_number = '5671235551234'
        expected = self.destination_four
        actual = parse_destination(phone_number, self.destinations)
        self.assertEqual(expected, actual)

    def test_none(self):
        phone_number = '7891235551234'
        expected = None
        actual = parse_destination(phone_number, self.destinations)
        self.assertEqual(expected, actual)
