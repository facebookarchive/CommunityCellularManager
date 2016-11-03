"""Tests for generating checkin data.

Usage:
    $ nosetests core.tests.checkin_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import unittest

from core.config_database import ConfigDB
import core.interconnect
import core.subscriber
from core.tests import mocks


class CheckinTest(unittest.TestCase):
    """We send valid data in a checkin."""

    @classmethod
    def setUpClass(cls):
        """Generate one set of checkin data to be analyzed in the tests."""
        # Mock the requests module so we don't actually POST.
        cls.original_requests = core.interconnect.requests
        cls.mock_requests = mocks.MockRequests(200)
        core.interconnect.requests = cls.mock_requests
        # Mock subscriber
        cls.original_subscriber = core.interconnect.subscriber
        core.interconnect.subscriber = mocks.MockSubscriber()

        # Mock core.events for generating usage events and handling the checkin
        # response.
        cls.original_events = core.interconnect.events
        core.interconnect.events = mocks.MockEvents()
        # Mock snowflake.
        cls.original_snowflake = core.interconnect.snowflake
        cls.mock_uuid = '09031a16-6361-4a93-a934-24c990ef4b87'
        core.interconnect.snowflake = mocks.MockSnowflake(cls.mock_uuid)
        # Mock BTS for TMSIs
        cls.original_bts = core.interconnect.bts
        core.interconnect.bts = mocks.MockBTS()
        # Mock a lot the package version numbers that should be sent in the
        # checkin.
        config_db = ConfigDB()
        cls.package_versions = {
            'endaga': '1.2.3',
            'freeswitch': '2.3.4',
            'gsm': '3.4.5',
            'python-endaga-core': '4.5.6',
            'python-gsm': '5.6.7',
        }
        for key in cls.package_versions:
            config_db['%s_version' % key] = cls.package_versions[key]
        # Mock psutil for system utilization stats.
        cls.original_psutil = core.system_utilities.psutil
        utilization = {
            'cpu_percent': 20.1,
            'memory_percent': 33.3,
            'disk_percent': 52.2,
            'bytes_sent': 1234,
            'bytes_received': 5678,
        }
        core.system_utilities.psutil = mocks.MockPSUtil(utilization)

        # Create some fake events
        es = core.interconnect.events.EventStore()
        es.add(cls.original_events._create_event(imsi="IMSI123", old_credit=0,
                new_credit=100, reason="Foo", write=False))
        es.add(cls.original_events._create_event(imsi="IMSI123", old_credit=0,
                new_credit=100, reason="Foo", write=False))
        es.add(cls.original_events._create_event(imsi="IMSI321", old_credit=0,
                new_credit=100, reason="Foo", write=False))

        # Setup a secret key.
        config_db['bts_secret'] = cls.mock_uuid
        # Attempt a checkin.
        config_db = core.config_database.ConfigDB()
        cls.endaga_ic = core.interconnect.endaga_ic(config_db)
        cls.endaga_ic.checkin()
        # Get the POSTed data and a deserialized form for convenience.
        cls.data = cls.mock_requests.post_data
        cls.deserialized_status = json.loads(cls.data['status'])

    @classmethod
    def tearDownClass(cls):
        """Repair the mocks."""
        core.interconnect.requests = cls.original_requests
        core.interconnect.events = cls.original_events
        core.interconnect.snowflake = cls.original_snowflake
        core.interconnect.bts = cls.original_bts
        core.interconnect.subscriber = cls.original_subscriber
        core.system_utilities.psutil = cls.original_psutil

    def test_uuid(self):
        """The BTS UUID should have been sent."""
        self.assertEqual(self.mock_uuid, self.data['bts_uuid'])

    def test_package_versions(self):
        """The package versions should have been sent."""
        for package in self.package_versions:
            self.assertEqual(
                self.package_versions[package],
                self.deserialized_status['versions'][package])

    def test_uptime(self):
        """The system uptime should be non-zero."""
        self.assertTrue(self.deserialized_status['uptime'] > 0)

    def test_tmsis(self):
        """The active subscribers from TMSIs should be sent."""
        self.assertEqual(3,
                         len(self.deserialized_status['camped_subscribers']))
        self.assertEqual(
            'IMSI901550000000083',
            self.deserialized_status['camped_subscribers'][0]['imsi'])

    def test_openbts_load(self):
        """Load data should be sent in the openbts_load section."""
        self.assertEqual(10, len(self.deserialized_status['openbts_load']))
        self.assertEqual(
            2, self.deserialized_status['openbts_load']['sdcch_load'])

    def test_openbts_noise(self):
        """Noise data should be sent in the openbts_noise section."""
        self.assertEqual(2, len(self.deserialized_status['openbts_noise']))
        self.assertEqual(
            -25, self.deserialized_status['openbts_noise']['noise_rssi_db'])

    def test_system_utilization_stats(self):
        """Various system utilization stats should be sent."""
        system_utilization = self.deserialized_status['system_utilization']
        self.assertEqual(20.1, system_utilization['cpu_percent'])
        self.assertEqual(33.3, system_utilization['memory_percent'])
        self.assertEqual(52.2, system_utilization['disk_percent'])
        # These initial byte deltas will be zero because 'checkin' has only
        # been called once so far (in the setUpClass).
        self.assertEqual(0, system_utilization['bytes_sent_delta'])
        self.assertEqual(0, system_utilization['bytes_received_delta'])
        # Setup the mock psutil again with different byte counts than those
        # established in setUpClass, and then checkin again.
        utilization = {
            'cpu_percent': 20.1,
            'memory_percent': 33.3,
            'disk_percent': 52.2,
            'bytes_sent': 1234 + 1000,
            'bytes_received': 5678 + 2000,
        }
        core.system_utilities.psutil = mocks.MockPSUtil(utilization)
        self.endaga_ic.checkin()
        data = self.mock_requests.post_data
        deserialized_status = json.loads(data['status'])
        system_utilization = deserialized_status['system_utilization']
        # The first checkin had bytes_sent as 1234, so we should see the delta
        # now (and similarly for bytes_received).
        self.assertEqual(1000, system_utilization['bytes_sent_delta'])
        self.assertEqual(2000, system_utilization['bytes_received_delta'])

    def test_subscribers(self):
        """ We should send info about our subscribers """
        self.assertTrue('subscribers' in self.deserialized_status)
        self.assertTrue('IMSI123' in self.deserialized_status['subscribers'])
        sub = self.deserialized_status['subscribers']['IMSI123']
        self.assertTrue('balance' in sub)
