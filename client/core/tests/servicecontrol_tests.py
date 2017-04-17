"""Tests for the system service controller.

Usage:
    $ nosetests core.tests.servicecontrol_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import unittest

from core.servicecontrol import BaseServiceControl, SystemControl, ServiceState
from core.service import Service

class TestServiceControl(BaseServiceControl):
    success_code = True

    def _runCommand(self, name, command):
        self.ranName = name
        self.ranCommand = command
        return self.success_code

    def stopProcess(self, name):
        """Stops a process by name."""
        return self._runCommand(name, "stop")

    def startProcess(self, name):
        """Starts a process by name."""
        return self._runCommand(name, "start")

    def restartProcess(self, name):
        """Restarts a process by name."""
        return self._runCommand(name, "restart")

    def status(self, name):
        """Gets process status."""
        is_running = self._runCommand(name, "status")
        if is_running:
            return ServiceState.Running
        else:
            return ServiceState.Error

class OtherServiceControl(SystemControl):
    pass

class ServiceControlTest(unittest.TestCase):
    """Service methods correctly excecute using the ServiceControl."""

    @classmethod
    def setUpClass(cls):
        cls.test_service = Service.SystemService("foo", controller=TestServiceControl)
        cls.service_ctl = cls.test_service.controller

    def setUp(self):
        """Clear the service control execute history"""
        self.service_ctl.success_code = True
        self.service_ctl.ranName = None
        self.service_ctl.ranCommand = None

    def test_start(self):
        result = self.test_service.start()
        self.assertTrue(result)
        self.assertEqual(self.service_ctl.ranCommand, "start")
        self.assertEqual(self.service_ctl.ranName, self.test_service.name)

    def test_stop(self):
        result = self.test_service.stop()
        self.assertTrue(result)
        self.assertEqual(self.service_ctl.ranCommand, "stop")
        self.assertEqual(self.service_ctl.ranName, self.test_service.name)

    def test_restart(self):
        result = self.test_service.restart()
        self.assertTrue(result)
        self.assertEqual(self.service_ctl.ranCommand, "restart")
        self.assertEqual(self.service_ctl.ranName, self.test_service.name)

    def test_status_running(self):
        status = self.test_service.status()
        self.assertEqual(status, ServiceState.Running)

    def test_status_error(self):
        self.service_ctl.success_code = False
        status = self.test_service.status()
        self.assertEqual(status, ServiceState.Error)

    def test_shared_connector(self):
        """Multiple instances of TestService share a Test service control."""
        test_service = Service.SystemService("foo", controller=TestServiceControl)
        self.assertEqual(test_service.controller, self.service_ctl)

    def test_unique_class_connector(self):
        """Each control class gets a unique shared connector."""
        other_service = Service.SystemService("foo", controller=OtherServiceControl)
        self.assertNotEqual(other_service.controller, self.service_ctl)
