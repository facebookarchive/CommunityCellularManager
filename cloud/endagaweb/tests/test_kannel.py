"""Testing the custom nexmo client.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from django.conf import settings
from django.test import TestCase
import mock

from endagaweb.ic_providers import kannel


class KannelProviderTestCase(TestCase):
    """Testing the custom Nexmo Provider client.

    We're using a Nexmo client from ic_providers that wraps our fork of
    libpynexmo.  Note that some client functionality would cost money if run
    against the live Nexmo API.

    These tests will not test libpynexmo.  They will *only* confirm that a
    request is properly formed and that return values are handled correctly.

    TODO(matt): tests for buying, setting up and releasing a number; tests for
                SMS.
    """

    def setUp(self):
        self.username = 'fake-username'
        self.passwd= 'fake-pw'
        self.inbound_url = None
        self.outbound_url = 'fake-api.endaga.com/cgi-bin/sendsms'
        self.voice_host = None
        # TODO(matt) test all supported countries
        self.country = "US"
        self.test_number = "01234567890"
        #we will mock out requests in order to faksies stuffsies
        self.kannel = kannel
        self.kannel.requests = mock.Mock()
        self.client = kannel.KannelProvider(self.username, self.passwd,
                                            self.inbound_url, self.outbound_url, 
                                            self.voice_host, country=self.country)

    def test_create_client(self):
        """We should be able to create a client."""
        self.assertTrue(isinstance(self.client, kannel.KannelProvider))

    def test_search_numbers(self):
        """Kannel doesn't do this"""
        with self.assertRaises(NotImplementedError):
            self.client.search_numbers()

    def test_buy_number(self):
        """Kannel doesn't do this"""
        with self.assertRaises(NotImplementedError):
            self.client.buy_number(self.test_number)

    def test_setup_number(self):
        """Kannel doesn't do this"""
        with self.assertRaises(NotImplementedError):
            self.client.setup_number(self.test_number)

    def test_cancel_number(self):
        """Kannel doesn't do this"""
        with self.assertRaises(NotImplementedError):
            self.client.cancel_number(self.test_number)

    def test_get_number(self):
        """Kannel doesn't do this"""
        with self.assertRaises(NotImplementedError):
            self.client.get_number(self.test_number)

    def test_get_number_info(self):
        """Kannel doesn't do this"""
        with self.assertRaises(NotImplementedError):
            self.client.get_number_info(self.test_number)

    def test_send_sms(self):
        """Send sms through kannel"""
        # Mock the requests response.
        self.kannel.requests.get.return_value = mock.Mock(status_code = 202)
        self.assertTrue(self.client.send("300", self.test_number, "test"))
        #pylint hates this
        #self.assertTrue(self.kannel.requests.get.called)
