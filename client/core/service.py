"""Managed system services.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from core.servicecontrol import (BaseServiceControl, SupervisorControl,
                                 SystemControl)
class Service(object):
    """A Managed system service."""

    def __init__(self, name, controller):
        if not isinstance(controller, BaseServiceControl):
            raise ValueError("Invalid service controller")
        self.name = name
        self.controller = controller

    def restart(self):
        """
        Restarts the service. This operation will block until the command is
        complete.
        """
        return self.controller.restartProcess(self.name)

    def start(self):
        """
        Starts the service. This operation will block until the command is
        complete.
        """
        return self.controller.startProcess(self.name)

    def stop(self):
        """
        Stops the service. This operation will block until the command is
        complete.
        """
        return self.controller.stopProcess(self.name)

    def status(self):
        """Return the ServiceState of the service"""
        return self.controller.status(self.name)

    @staticmethod
    def SupervisorService(name, controller=SupervisorControl):
        """Returns a supervisord managed Service"""
        return Service(name, controller.instance())

    @staticmethod
    def SystemService(name, controller=SystemControl):
        """Returns a systemd managed service"""
        return Service(name, controller.instance())
