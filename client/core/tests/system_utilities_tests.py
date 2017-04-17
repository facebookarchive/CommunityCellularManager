"""Tests for system utilities

Usage:
    $ nosetests core.tests.system_utilities_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import unittest

import mock

import core
from core import config_database
from core.system_utilities import uptime
from core import system_utilities
from core.system_utilities import get_fs_profile_ip
from core.tests.mocks import MockDelegator


class SystemUtilitiesTest(unittest.TestCase):
    def test_uptime(self):
        self.assertTrue(uptime() > 0)


class AutoupgradeTest(unittest.TestCase):
    """Testing the autoupgrade methods."""

    @classmethod
    def setUpClass(cls):
        cls.config_db = config_database.ConfigDB()
        cls.upgrade_method = 'core.system_utilities.upgrade_endaga'
        cls.config_db['registration_interval'] = 60

    def setUp(self):
        self.config_db['autoupgrade.enabled'] = True
        self.config_db['endaga_version'] = '1.2.3'
        self.config_db['autoupgrade.in_window'] = False
        self.config_db['autoupgrade.last_upgrade'] = '2015-07-14 02:30:15'

    def test_disabled(self):
        """If autoupgrade is disabled, we should not try to upgrade."""
        self.config_db['autoupgrade.enabled'] = False
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(False, mock_upgrade.called)

    def test_no_new_version(self):
        """We don't autoupgrade if a new version isn't available."""
        self.config_db['autoupgrade.channel'] = 'beta'
        self.config_db['autoupgrade.latest_beta_version'] = '1.2.3'
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(False, mock_upgrade.called)

    def test_immediate(self):
        """We can upgrade as soon as a new package is available."""
        self.config_db['autoupgrade.channel'] = 'beta'
        self.config_db['autoupgrade.latest_beta_version'] = '3.2.1'
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(True, mock_upgrade.called)
        # A new version is suddenly available, and we can upgrade again.
        self.config_db['autoupgrade.latest_beta_version'] = '3.2.2'
        with mock.patch(self.upgrade_method) as second_mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(True, second_mock_upgrade.called)

    def test_not_in_window(self):
        """Don't upgrade if we're not in the window."""
        self.config_db['autoupgrade.in_window'] = True
        # Set the window to a few hours from now.
        the_future = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        self.config_db['autoupgrade.window_start'] = (
            the_future.strftime('%H:%M:%S'))
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(False, mock_upgrade.called)

    def test_just_before_window(self):
        """Don't upgrade if the window hasn't quite started."""
        self.config_db['autoupgrade.in_window'] = True
        # Set the window to start a second from now.
        the_future = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        self.config_db['autoupgrade.window_start'] = (
            the_future.strftime('%H:%M:%S'))
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(False, mock_upgrade.called)

    def test_just_after_window(self):
        """Don't upgrade if the window has just passed."""
        self.config_db['autoupgrade.in_window'] = True
        # Set the window to have started duration + a second before now.
        the_past = datetime.datetime.utcnow() - datetime.timedelta(seconds=601)
        self.config_db['autoupgrade.window_start'] = (
            the_past.strftime('%H:%M:%S'))
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(False, mock_upgrade.called)

    def test_correct_window(self):
        """Upgrade if we're in the correct window."""
        self.config_db['autoupgrade.in_window'] = True
        # Set the upgrade window to have started a second before now.
        the_past = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        self.config_db['autoupgrade.window_start'] = (
            the_past.strftime('%H:%M:%S'))
        # Setup a specific upgrade channel.
        self.config_db['autoupgrade.channel'] = 'beta'
        self.config_db['autoupgrade.latest_beta_version'] = '3.4.5'
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        # The upgrade command should be called with a specific channel.
        self.assertEqual(True, mock_upgrade.called)
        args, _ = mock_upgrade.call_args
        self.assertEqual('beta', args[0])

    def test_back_to_back(self):
        """We won't upgrade twice in a short period of time."""
        self.config_db['autoupgrade.in_window'] = True
        self.config_db['autoupgrade.channel'] = 'beta'
        self.config_db['autoupgrade.latest_beta_version'] = '3.4.5'
        # Set the upgrade window to have started a second before now.
        the_past = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
        self.config_db['autoupgrade.window_start'] = (
            the_past.strftime('%H:%M:%S'))
        with mock.patch(self.upgrade_method) as mock_upgrade:
            system_utilities.try_to_autoupgrade()
        # The upgrade command should be called.
        self.assertEqual(True, mock_upgrade.called)
        # But another attempt to ugprade will be blocked.
        with mock.patch(self.upgrade_method) as second_mock_upgrade:
            system_utilities.try_to_autoupgrade()
        self.assertEqual(False, second_mock_upgrade.called)


class ExternalProfileIPTest(unittest.TestCase):
    """Tests our ability to get the external profile's IP from FS."""

    @classmethod
    def setUpClass(cls):
        """Monkeypatch the delegator return value."""
        with open('core/tests/fixtures/sofia-status-output.txt') as output:
            return_text = output.read()
        mock_delegator = MockDelegator(return_text)
        cls.original_delegator = core.system_utilities.delegator
        core.system_utilities.delegator = mock_delegator

    @classmethod
    def tearDownClass(cls):
        """Repair the monkeypatch."""
        core.system_utilities.delegator = cls.original_delegator

    def test_external(self):
        """We can get data for the 'external' profile."""
        self.assertEqual('10.64.0.38', get_fs_profile_ip('external'))

    def test_openbts(self):
        """We can get data for the 'openbts' profile."""
        self.assertEqual('127.0.0.1', get_fs_profile_ip('openbts'))
