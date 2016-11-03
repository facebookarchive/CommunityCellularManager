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

from endagaweb.ic_providers import nexmo


class NexmoProviderTestCase(TestCase):
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
        self.acct_id = 'fake-username'
        self.token = 'fake-pw'
        self.inbound_url = 'fake-api.endaga.com/api/v1/sms'
        self.outbound_url = None
        self.voice_host = 'fake-sip.endaga.com'
        # TODO(matt) test all supported countries
        self.country = "US"
        self.test_number = "01234567890"
        # We will mock the libpynexmo package used by the client module.  This
        # allows us to intercept messages and mock return values.
        self.nexmo = nexmo
        self.nexmo.NexmoMessage = mock.Mock()
        self.client = nexmo.NexmoProvider(self.acct_id, self.token,
                                          self.inbound_url, self.outbound_url, 
                                          self.voice_host, country=self.country)

    def test_create_client(self):
        """We should be able to create a client."""
        self.assertTrue(isinstance(self.client, nexmo.NexmoProvider))

    def test_search_request_well_formed(self):
        # Mock the Nexmo response.
        self.nexmo.NexmoMessage.return_value.send_request.return_value = {
            'numbers': [
                {'msisdn': 456}
            ]
        }
        self.client.search_numbers()
        # The mocks here end up a bit strange.  We verify that the NexmoMessage
        # was called with the request dict below.  The weird syntax that is
        # required here may be because we do NexmoMessage(req).send_request()
        # (the instantiate-and-immediately-call-a-method pattern).
        expected_call = mock.call({
            'username': self.acct_id,
            'password': self.token,
            'type': 'search',
            'country': self.country,
            'features': 'SMS,VOICE'
        })
        self.assertIn(expected_call, self.nexmo.NexmoMessage.mock_calls)

    def test_search_returns_numbers(self):
        """We should be able to parse the response during numbers search."""
        # Mock the Nexmo response.
        self.nexmo.NexmoMessage.return_value.send_request.return_value = {
            'numbers': [
                {'msisdn': 123},
                {'msisdn': 456}
            ]
        }
        result = self.client.search_numbers()
        self.assertTrue(isinstance(result, int))

    def test_no_numbers_available_during_search(self):
        # Mock the Nexmo response.
        self.nexmo.NexmoMessage.return_value.send_request.return_value = {
            'numbers': []
        }
        with self.assertRaises(ValueError):
            self.client.search_numbers()

    def test_setup_number(self):
        # Mock the Nexmo response.
        self.nexmo.NexmoMessage.return_value.send_request.return_value = {
            'code': 200
        }
        result = self.client.setup_number(self.test_number)
        self.assertTrue(result)

    def test_get_number_info(self):
        """We should be able to setup a number and get info about it."""
        # Assume the number has been setup already and mock the Nexmo response
        # to client.get_number_info.
        # TODO(matt): mocking here is kinda silly..we setup the perfect response
        #             and then verify that the response is indeed perfect.
        self.nexmo.NexmoMessage.return_value.send_request.return_value = {
            'numbers': [{
                'msisdn': self.test_number,
                'features': ['VOICE', 'SMS'],
                'moHttpUrl': self.inbound_url,
                'voiceCallbackType': 'sip',
                'voiceCallbackValue': '%s@%s' % (self.test_number,
                                                 self.voice_host)
            }]
        }
        info = self.client.get_number_info(self.test_number)
        self.assertTrue(len(info) == 1)
        num_info = info[self.test_number]
        self.assertIn("VOICE", num_info['features'])
        self.assertIn("SMS", num_info['features'])
        self.assertTrue(num_info['moHttpUrl'] == self.inbound_url)
        self.assertTrue(num_info['voiceCallbackType'] == 'sip')
        expected_voice_callback_value = "%s@%s" % (self.test_number,
                                                   self.voice_host)
        self.assertTrue(num_info['voiceCallbackValue'] ==
                        expected_voice_callback_value)

    def test_send_sms(self):
        """Send sms to Nexmo"""
        # Mock the Nexmo response.
        self.nexmo.NexmoMessage.return_value.send_request.return_value = {
            'message-count': '1',
            'messages' : [{'status' : '0'}]
        }
        self.assertTrue(self.client.send("300", self.test_number, ""))
