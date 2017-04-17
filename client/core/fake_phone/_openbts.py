"""A library for simulating a user's phone.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import random
import string
from threading import Thread

#sms imports
import sms_utilities
from smspdu import SMS_DELIVER
from twisted.internet import reactor
from twisted.protocols import sip
from twisted.internet.protocol import ServerFactory
from twisted.protocols.sip import Request

#fs call imports
from ESL import ESLconnection
from core.config_database import ConfigDB

from .base import BaseFakePhone


SIP_PORT = 5060
SIP_REG_PORT = 5064


def genTag(length):
    return ''.join(random.choice(string.ascii_lowercase + string.digits)
                   for _ in range(length))


def genCallId():
    return (genTag(8) + "-" + genTag(4) + "-" + genTag(4) + "-" + genTag(4) +
            "-" + genTag(12))


class SipProxy(sip.Proxy):

    def __init__(self, user, port, call_handler, sms_handler,
                 self_ip, other_ip):
        self.port = port
        self.self_ip = self_ip
        self.other_ip = other_ip
        self.user = user
        self.call_h = call_handler
        self.sms_h = sms_handler
        sip.Proxy.__init__(self, host=self.self_ip, port=port)

    def handle_response(self, message, addr):
        if message.code == 401:
            print("REGISTER REJECTED, DISABLE AUTH IN SIPAUTH")
            print("INSERT INTO \"CONFIG\" VALUES('SubscriberRegistry"
                   ".IgnoreAuthentication','1',0,1,'Disable Auth');")
        else:
            print("RESPONSE: " + str(message.code))

    def handle_request(self, message, addr):
        to = message.uri.username
        fromm = sip.parseAddress(message.headers['from'][0])[1].username
        if message.method == 'MESSAGE':
            rpdu = sms_utilities.rpdu.RPDU.fromPDU(message.body)
            sms_deliver = SMS_DELIVER.fromPDU(rpdu.user_data,
                                              rpdu.rp_originator_address)
            self.sms_h(to, fromm, sms_deliver.user_data)
            r = self.responseFromRequest(200, message)
        elif message.method == 'ACK':
            r = self.responseFromRequest(200, message)
        elif message.method == 'INVITE':
            self.call_h(to, fromm)
            # We don't know how to actually handle calls.
            r = self.responseFromRequest(487, message)
        else:
            raise Exception("Received unhandled request")
        self.deliverResponse(r)

    def startProtocol(self):
        """On startup, send a REGISTER message to sipauthserve.

        Explicitly use less fields than OpenBTS: want to enforce the right to:
        field.
        """
        r = Request("REGISTER", "sip:%s@%s:%s" %
                    (self.user, self.other_ip, SIP_REG_PORT))
        r.addHeader("Via", "SIP/2.0/UDP %s:%s;branch=%s;received=%s;rport=%s" %
                    (self.self_ip, self.port, genTag(22), self.self_ip,
                     self.port))
        r.addHeader("From", "<sip:%s@%s:%s>;tag=%s" %
                    (self.user, self.self_ip, self.port, genTag(13)))
        r.addHeader("To", "<sip:%s@%s:%s>" % (self.user, self.other_ip,
                                              self.port))
        r.addHeader("Contact", "<sip:%s:%s>" % (self.self_ip, self.port))
        r.addHeader("User-Agent", "Endaga-test")
        self.sendMessage(sip.URL(host=self.other_ip, port=SIP_REG_PORT), r)

    def sendSMS(self, dest, content):
        content = sms_utilities.SMS_Submit.gen_msg(str(dest), content, False)
        r = Request("MESSAGE", "sip:smsc@%s:%s" % (self.other_ip, SIP_PORT))
        r.addHeader("Via", "SIP/2.0/UDP %s:%s;branch=%s;received=%s;rport=%s" %
                    (self.self_ip, self.port, genTag(22), self.self_ip,
                     self.port))
        r.addHeader("Max-Forwards", "70")
        r.addHeader("From", "<sip:%s@%s:%s>;tag=%s" %
                    (self.user, self.self_ip, self.port, genTag(13)))
        r.addHeader("To", "<sip:smsc@%s:%s>" % (self.other_ip, self.port))
        r.addHeader("Call-ID", genCallId())
        r.addHeader("CSeq", "1 MESSAGE")
        r.addHeader("Contact", "<sip:%s:%s>" % (self.self_ip, SIP_PORT))
        r.addHeader("User-Agent", "Endaga-test")
        r.addHeader("Content-Type", "application/vnd.3gpp.sms")
        r.addHeader("Content-Length", str(len(content)))
        r.body = content
        self.sendMessage(sip.URL(host=self.other_ip, port=SIP_PORT), r)


class sipfactory(ServerFactory):
    protocol = SipProxy


class OpenBTSFakePhone(BaseFakePhone):
    reactorRunning = False

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
        self.proxy = SipProxy(self.user, self.port, self.call_h, self.sms_h,
                              self.self_ip, self.other_ip)
        reactor.listenUDP(self.port, self.proxy, self.self_ip)
        if not OpenBTSFakePhone.reactorRunning:
            OpenBTSFakePhone.reactorRunning = True
            Thread(target=reactor.run, args=(False,)).start()

    def stop(self):
        if OpenBTSFakePhone.reactorRunning:
            OpenBTSFakePhone.reactorRunning = False
            reactor.callFromThread(reactor.stop)

    def sendSMS(self, destination, content):
        reactor.callFromThread(self.proxy.sendSMS, destination, content)

    def makeCall(self, destination):
        con = ESLconnection(self.conf['fs_esl_ip'], self.conf['fs_esl_port'],
                            self.conf['fs_esl_pass'])
        if con.connected():
            con.api(str("originate {origination_call_id_name=%s,origination"
                        "_caller_id_number=%s}sofia/internal/%s@%s:"
                        "5060 &echo" % (self.user, self.user, destination,
                                        self.other_ip)))
        else:
            raise Exception("ESL Connection Failed")
