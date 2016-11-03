"""A library for simulating a user's phone.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""
import json

from core.config_database import ConfigDB

class BaseFakePhone:

    def __init__(self, user, port, call_handler, sms_handler,
                 self_ip="127.0.0.1", other_ip="127.0.0.1"):
        #add user to the fakebts list of camped subscribers
        self.conf = ConfigDB()
        if 'fakebts.camped' not in self.conf:
            self.conf['fakebts.camped'] = json.dumps([])
        self.conf['fakebts.camped'] = json.dumps(json.loads(self.conf['fakebts.camped']) + [user])

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def sendSMS(self, destination, content):
        raise NotImplementedError()

    def makeCall(self, destination):
        raise NotImplementedError()
