"""Testing UsageEvent parsing for GPRS events.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

from endagaweb.util import parse_usage_event


class ReasonTest(unittest.TestCase):
    """Testing util.parse_usage_event.parse_gprs_reason."""

    def test_one(self):
        reason = 'gprs_usage: 184 bytes uploaded, 0 bytes downloaded'
        expected = (184, 0)
        self.assertEqual(expected, parse_usage_event.parse_gprs_reason(reason))

    def test_two(self):
        reason = 'gprs_usage: 3730 bytes uploaded, 22107 bytes downloaded'
        expected = (3730, 22107)
        self.assertEqual(expected, parse_usage_event.parse_gprs_reason(reason))

    def test_three(self):
        reason = 'gprs_usage: 0 bytes uploaded, 0 bytes downloaded'
        expected = (0, 0)
        self.assertEqual(expected, parse_usage_event.parse_gprs_reason(reason))

    def test_empty_reason(self):
        """There was an event with an empty reason, for some reason.."""
        reason = ''
        expected = (0, 0)
        self.assertEqual(expected, parse_usage_event.parse_gprs_reason(reason))
