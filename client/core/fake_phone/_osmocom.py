"""A library for simulating a user's phone.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from ESL import ESLconnection
from core.config_database import ConfigDB
from core.subscriber import subscriber

from .base import BaseFakePhone

SMPP_PORT = 2775
SMPP_USER = 'OSMPP'
SMPP_PASSWORD = 'etagecom'


class OsmocomFakePhone(BaseFakePhone):

    def __init__(self, user, port, call_handler, sms_handler,
                 self_ip="127.0.0.1", other_ip="127.0.0.1"):
        BaseFakePhone.__init__(self, user, port, call_handler, sms_handler,
                               self_ip=self_ip, other_ip=other_ip)
        self.user = user
        self.conf = ConfigDB()
        self.port = port
        self.sms_h = sms_handler
        self.call_h = call_handler
        self.self_ip = self_ip
        self.other_ip = other_ip

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def sendSMS(self, destination, content):
        raise NotImplementedError()

    def makeCall(self, destination):
        username = subscriber.get_username_from_imsi(self.user)
        con = ESLconnection(self.conf['fs_esl_ip'], self.conf['fs_esl_port'],
                            self.conf['fs_esl_pass'])
        if con.connected():
            con.api(str("originate {origination_call_id_name=%s,origination"
                        "_caller_id_number=%s}sofia/internal/%s@%s:%s"
                        "5062 &echo" % (username, username, destination,
                                        self.other_ip)))
        else:
            raise Exception("ESL Connection Failed")
