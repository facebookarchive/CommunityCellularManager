"""System service controllers.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import abc
from enum import Enum
import delegator
from supervisor.xmlrpc import SupervisorTransport
import xmlrpc.client

from ccm.common import logger

class ServiceState(Enum):
    Running = 1
    Error = 2


class BaseServiceControl(object, metaclass=abc.ABCMeta):
    """
    Service Control is the interface to managing services and their state. This
    allows us to start system services after system provisiong, and probe
    service state to monitor service health and issue restarts on failures.
    """
    __instance = None

    @abc.abstractmethod
    def startProcess(self, name):
        """
        Start a process by name and return success boolean
        """
        pass

    @abc.abstractmethod
    def stopProcess(self, name):
        """
        Stop a process by name and return a success boolean
        """
        pass

    @abc.abstractmethod
    def restartProcess(self, name):
        """
        Restart a process by name and return success boolean
        """
        pass

    @abc.abstractmethod
    def status(self, name):
        """
        Return the ServiceState of the service by name
        """
        pass

    @classmethod
    def instance(cls):
        """
        Returns a shared controller instance that is used across the process.
        We only want one control instance to be managing Services, especially
        if the controller must maintain a socket.
        """
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance


class SupervisorControl(BaseServiceControl):
    """Controller for supervisord managed services. Commands are issued
    using the supervisor XML RPC and block until they are completed.
    """

    def __init__(self):
        t = SupervisorTransport(None, None, "unix:///var/run/supervisor.sock")
        self.server = xmlrpc.client.ServerProxy("http://127.0.0.1", transport=t)

    def stopProcess(self, name):
        """Stops a process by name."""
        try:
            logger.info("Supervisor: stopping %s" % name)
            return self.server.supervisor.stopProcess(name)
        except xmlrpc.client.Fault as e:
            if e.faultCode == 70:  # NOT_RUNNING
                return True
            logger.error("Supervisor: failed to stop %s, fault code: %d" %
                         (name, e.faultCode))
            return False
        except IOError:
            logger.error("Supervisor: stop %s failed due to ioerror" % name)
            return False

    def startProcess(self, name):
        """Starts a process by name."""
        try:
            logger.info("Supervisor: starting %s" % name)
            return self.server.supervisor.startProcess(name)
        except xmlrpc.client.Fault as e:
            if e.faultCode == 60:  # ALREADY_STARTED
                logger.info("Supervisor: %s already started" % name)
                return True
            logger.error("Supervisor: failed to start %s, fault code: %d" %
                         (name, e.faultCode))
            return False
        except IOError:
            logger.error("Supervisor: start %s failed due to ioerror" % name)
            return False

    def restartProcess(self, name):
        """Restart a process by name"""
        stop_result = self.stopProcess(name)
        return self.startProcess(name) and stop_result

    def status(self, name):
        """Gets process status."""
        try:
            status = self.server.supervisor.getProcessInfo(name)
            state = status.get('statename', 'ERROR')
            if state == 'RUNNING':
                return ServiceState.Running
            else:
                return ServiceState.Error
        except xmlrpc.client.Fault:
            return ServiceState.Error


class SystemControl(BaseServiceControl):
    """Control for managing systemd services. Issues shell commands and blocks
    until completion"""
    def __init__(self):
        self.cmd = None # service or systemctl

    def _runCommand(self, name, command):
        if not self.cmd:
            try:
                r = delegator.run("systemctl --version")
                if r.return_code == 0:
                    self.cmd = "systemctl"
                else:
                    self.cmd = "service"
            except BaseException as e:
                logger.error("delegator systemctl exception %s" % e)
                self.cmd = "service"

        if self.cmd == "systemctl":
            r = delegator.run("sudo systemctl %s %s" % (command, name))
        else:
            r = delegator.run("sudo service %s %s" % (name, command))
        result = r.return_code == 0
        return result

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


BaseServiceControl.register(SupervisorControl)
BaseServiceControl.register(SystemControl)
