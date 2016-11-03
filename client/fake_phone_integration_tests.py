"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Tests for FS using core.fake_phone

Note that the test cases run in a particular order via the naming of each
class.  We do this because the fake phone twisted reactor should be made to
start just once and stop just once.

Run this test from the project root
    $ nosetests core.tests.phone_tests
"""

from threading import Thread
import json
import sys
import time
import unittest

from core.config_database import ConfigDB
import core.fake_phone as fake_phone
from core.subscriber import subscriber
from core.subscriber.base import SubscriberNotFound
import core.tests.mock_api


def sleep_until(predicate, timeout):
    """Small timeout utility to sleep until a predicate is satisfied."""
    for _ in range(timeout):
        if predicate():
            break
        time.sleep(1)


def call_handler(fp):
    print ("Call Received")
    fp.call_received = True


def sms_handler(fp, content):
    print ("SMS Received: " + content)
    fp.sms_received = True
    fp.content = content


CONF = ConfigDB()
FEDERER_TIMEOUT = 15  # seconds
SMQ_TIMEOUT = 15  # seconds
FS_TIMEOUT = 15  # seconds


class FakePhoneTest_01_Nominal(unittest.TestCase):
    """Testing FS functionality"""

    @classmethod
    def setUpClass(cls):
        # Mock the Endaga API endpoint in a new process.
        cls.webserver = Thread(
            target=core.tests.mock_api.APP_NOMINAL.run)
        # This is a kludge -- web.py is strict on taking the port from argv.
        sys.argv = ['8080']
        cls.webserver.setDaemon(True)
        cls.webserver.start()
        # Wait for the server to start.
        sleep_until(cls.webserver.is_alive, FEDERER_TIMEOUT)
        # Set the API endpoint system wide.
        cls.old_registry = CONF['registry']
        CONF['registry'] = 'http://127.0.0.1:8080'
        # Setup two FakePhones.
        cls.fp1 = fake_phone.FakePhone(
            "IMSI901559000000002", 5066,
            lambda to, fromm: call_handler(cls.fp1),
            lambda to, fromm, content: sms_handler(cls.fp1, content))
        cls.fp2 = fake_phone.FakePhone(
            "IMSI901559000000003", 5067,
            lambda to, fromm: call_handler(cls.fp2),
            lambda to, fromm, content: sms_handler(cls.fp2, content))
        for phone in [cls.fp1, cls.fp2]:
            phone.sms_received = False
            phone.content = ''
            phone.credits = ''
            phone.number = None
        cls.fp1.start()
        cls.fp2.start()
        # Make sure the SR is starting afresh.
        for phone in [cls.fp1, cls.fp2]:
            subscriber.delete_subscriber(phone.user)
        # Register each phone by texting 101.
        for phone in [cls.fp1, cls.fp2]:
            phone.sms_received = False
            phone.sendSMS("101", "register me!")
            sleep_until(lambda: phone.sms_received, FEDERER_TIMEOUT)
            phone.number = phone.content[-12:-1]

    @classmethod
    def tearDownClass(cls):
        # Terminate the mock API process.
        core.tests.mock_api.APP_NOMINAL.stop()
        # Restore the old registry endpoint.
        CONF['registry'] = cls.old_registry
        # Deregister the users.
        for phone in [cls.fp1, cls.fp2]:
            subscriber.delete_subscriber(phone.user)

    def setUp(self):
        """Reset each fake phone client before each test."""
        for phone in [self.fp1, self.fp2]:
            phone.call_received = False
            phone.sms_received = False
            phone.content = ''
            phone.credits = ''
            try:
                subscriber._set_credit(phone.user, '0')
            except SubscriberNotFound:
                pass

    @staticmethod
    def _set_credit(user, balance):
        credits = json.dumps({'p': {'pn1': balance}, 'n': {}})
        subscriber._set_credit(user, credits)

    def test_01_not_provisioned(self):
        """Should get a "not-provisioned" message before registration."""
        # First delete the sub.
        subscriber.delete_subscriber(self.fp1.user)
        # Then try a credit check.
        self.fp1.sendSMS(CONF['credit_check_number'], "not provisioned")
        sleep_until(lambda p=self.fp1: p.sms_received, FS_TIMEOUT)
        self.assertEqual(self.fp1.content, "Your phone is not provisioned.")

    def test_02_provisioning(self):
        """We can text 101 to register."""
        # First delete the sub.
        subscriber.delete_subscriber(self.fp1.user)
        # Then try to register.
        self.fp1.sendSMS("101", "register me!")
        sleep_until(lambda: self.fp1.sms_received, FEDERER_TIMEOUT)
        self.assertEqual(self.fp1.content[:14], "Your number is")
        self.fp1.number = self.fp1.content[-12:-1]
        self.assertEqual(len(self.fp1.number), 11)
        self.assertEqual(
            1, len(subscriber.get_subscribers(imsi=self.fp1.user)))

    def test_03_sms_number_check(self):
        """An MS can determine its number by texting number check."""
        self.fp1.sendSMS(CONF['number_check_number'], "number")
        sleep_until(lambda: self.fp1.sms_received, SMQ_TIMEOUT)
        self.assertTrue(self.fp1.sms_received)
        self.assertEqual(
            self.fp1.content, "Your number is %s." % self.fp1.number)

    def test_04_call_number_check(self):
        """An MS can determine its number by calling number check."""
        self.fp2.makeCall(CONF['number_check_number'])
        sleep_until(lambda: self.fp2.sms_received, SMQ_TIMEOUT)
        self.assertEqual(
            self.fp2.content, "Your number is %s." % self.fp2.number)

    def test_05_sms_credit_check(self):
        """An MS can check its credit balance by texting credit check."""
        # First give some credit to the account.
        self._set_credit(self.fp2.user, 5432000)
        # Then send the credit check message.
        self.fp2.sendSMS(CONF['credit_check_number'], 'what is my balance')
        sleep_until(lambda: self.fp2.sms_received, SMQ_TIMEOUT)
        self.assertEqual(
            self.fp2.content, "Your balance is $54.32.")

    def test_06_call_credit_check(self):
        """An MS can check its credit balance by calling credit check."""
        # First give some credit to the account.
        self._set_credit(self.fp2.user, 12345)
        # Then make the credit check call.
        self.fp2.makeCall(CONF['credit_check_number'])
        sleep_until(lambda: self.fp2.sms_received, SMQ_TIMEOUT)
        self.assertEqual(
            self.fp2.content, "Your balance is $0.12.")

    def test_07_sms_no_credit(self):
        """Cannot send an SMS if the user has no credit."""
        self._set_credit(self.fp2.user, 0)
        cur_cost = CONF['prices.on_network_send.cost_to_subscriber_per_sms']
        CONF['prices.on_network_send.cost_to_subscriber_per_sms'] = 200
        self.fp2.sendSMS(str(self.fp1.number), "im broke!")
        sleep_until(lambda: self.fp1.sms_received, SMQ_TIMEOUT)
        CONF['prices.on_network_send.cost_to_subscriber_per_sms'] = cur_cost
        self.assertEqual(
            self.fp2.content, "Your account doesn't have sufficient funds to send an SMS.")

    def test_08_call_no_credit(self):
        """Cannot make a call if the user has no credit."""
        self._set_credit(self.fp2.user, 0)
        cur_cost = CONF['prices.on_network_send.cost_to_subscriber_per_min']
        CONF['prices.on_network_send.cost_to_subscriber_per_min'] = 200
        self.fp2.makeCall(str(self.fp1.number))
        sleep_until(lambda: self.fp2.sms_received, SMQ_TIMEOUT)
        CONF['prices.on_network_send.cost_to_subscriber_per_min'] = cur_cost
        self.assertEqual(
            self.fp2.content, "Your account doesn't have sufficient funds.")

    def test_09_sms(self):
        """We can send an SMS."""
        self._set_credit(self.fp1.user, 1000000)
        content = 'hello phone one'
        self.fp1.sendSMS(str(self.fp2.number), content)
        sleep_until(lambda: self.fp2.sms_received, SMQ_TIMEOUT)
        self.assertEqual(self.fp2.content, content)

    def test_10_call(self):
        """We can make a call."""
        self._set_credit(self.fp1.user, 1000000)
        self.fp1.makeCall(self.fp2.number)
        sleep_until(lambda: self.fp2.call_received, FS_TIMEOUT)
        self.assertTrue(self.fp2.call_received)


class FakePhoneTest_02_FailedNumberAllocation(unittest.TestCase):
    """Testing a failed number allocation on provisioning"""

    @classmethod
    def setUpClass(cls):
        # Mock the Endaga API endpoint in a new process.
        cls.webserver = Thread(
            target=core.tests.mock_api.APP_BAD_NUMBER_ALLOCATION.run)
        # This is a kludge -- web.py is strict on taking the port from argv.
        sys.argv = ['8080']
        cls.webserver.setDaemon(True)
        cls.webserver.start()
        # Wait for the server to start.
        sleep_until(cls.webserver.is_alive, FEDERER_TIMEOUT)
        # Set the API endpoint system wide.
        cls.old_registry = CONF['registry']
        CONF['registry'] = 'http://127.0.0.1:8080'
        # Setup a FakePhone.
        cls.fp1 = fake_phone.FakePhone(
            "IMSI901559000000002", 5068,
            lambda to, fromm: call_handler(cls.fp1),
            lambda to, fromm, content: sms_handler(cls.fp1, content))
        cls.fp1.start()
        # Make sure the SR is starting afresh.
        subscriber.delete_subscriber(cls.fp1.user)

    @classmethod
    def tearDownClass(cls):
        # Terminate the mock API process.
        core.tests.mock_api.APP_BAD_NUMBER_ALLOCATION.stop()
        # Restore the old registry endpoint.
        CONF['registry'] = cls.old_registry
        # Deregister the user.
        subscriber.delete_subscriber(cls.fp1.user)

    def setUp(self):
        """Reset each fake phone client before each test."""
        self.fp1.call_received = False
        self.fp1.sms_received = False
        self.fp1.content = ''
        self.fp1.credits = ''

    def test_failed_provisioning_no_numbers(self):
        """When we fail to get a new number we let the sub know we failed."""
        # Try to register.
        self.fp1.sendSMS("101", "give me a number!")
        sleep_until(lambda: self.fp1.sms_received, FEDERER_TIMEOUT)
        self.assertEqual(self.fp1.content, "Failed to register your handset.")


class FakePhoneTest_03_FailedRegistration(unittest.TestCase):
    """Testing a failed registration on provisioning"""

    @classmethod
    def setUpClass(cls):
        # Mock the Endaga API endpoint in a new process.
        cls.webserver = Thread(
            target=core.tests.mock_api.APP_BAD_REGISTRATION.run)
        # This is a kludge -- web.py is strict on taking the port from argv.
        sys.argv = ['8080']
        cls.webserver.setDaemon(True)
        cls.webserver.start()
        # Wait for the server to start.
        sleep_until(cls.webserver.is_alive, FEDERER_TIMEOUT)
        # Set the API endpoint system wide.
        cls.old_registry = CONF['registry']
        CONF['registry'] = 'http://127.0.0.1:8080'
        # Setup a FakePhone.
        cls.fp1 = fake_phone.FakePhone(
            "IMSI901559000000002", 5069,
            lambda to, fromm: call_handler(cls.fp1),
            lambda to, fromm, content: sms_handler(cls.fp1, content))
        cls.fp1.start()
        # Make sure the SR is starting afresh.
        subscriber.delete_subscriber(cls.fp1.user)

    @classmethod
    def tearDownClass(cls):
        # Terminate the mock API process.
        core.tests.mock_api.APP_BAD_REGISTRATION.stop()
        # Restore the old registry endpoint.
        CONF['registry'] = cls.old_registry
        # Deregister the user.
        subscriber.delete_subscriber(cls.fp1.user)
        # Note: Only in the last test case do we tear down the reactor.
        cls.fp1.stop()

    def setUp(self):
        """Reset each fake phone client before each test."""
        self.fp1.call_received = False
        self.fp1.sms_received = False
        self.fp1.content = ''
        self.fp1.credits = ''

    def test_failed_provisioning_bad_registration(self):
        """When we fail to register, let the sub know we failed."""
        # Try to register.
        self.fp1.sendSMS("101", "give me a number!")
        sleep_until(lambda: self.fp1.sms_received, FEDERER_TIMEOUT)
        self.assertEqual(self.fp1.content, "Failed to register your handset.")
