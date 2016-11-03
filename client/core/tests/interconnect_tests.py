"""Testing core.interconnect.

Usage:
    $ nosetests core.tests.interconnect_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

import mock

from core import interconnect
from core.config_database import ConfigDB
from core.tests import mocks


class EndagaICTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Setup the ConfigDB with a fake secret, and mock other items."""
        cls.config_db = ConfigDB()
        cls.config_db['bts_secret'] = 'test-secret-123'
        cls.original_logger = interconnect.logger
        cls.mock_logger = mock.Mock()
        interconnect.logger = cls.mock_logger
        # Mock bts for TMSIs
        cls.original_bts = interconnect.bts
        interconnect.bts = mocks.MockBTS()
        # Mock subscriber
        cls.original_subscriber = interconnect.subscriber
        interconnect.subscriber = mocks.MockSubscriber()

    @classmethod
    def tearDownClass(cls):
        """Repair the monkeypatches."""
        interconnect.logger = cls.original_logger
        interconnect.bts = cls.original_bts
        interconnect.subscriber = cls.original_subscriber

    def test_checkin_logging_if_post_fails(self):
        # Hook up the mock requests and log module, then instantiate an IC.
        original_requests = interconnect.requests
        return_code = 400
        interconnect.requests = mocks.MockRequests(return_code)
        ic = interconnect.endaga_ic(self.config_db)
        ic.checkin()
        # With this failing return code, we expect the checkin to trigger a
        # call to the logger error method of the mocked logger module.
        self.assertTrue(self.mock_logger.error.called)
        # Repair the requests monkeypatch.
        interconnect.requests = original_requests
