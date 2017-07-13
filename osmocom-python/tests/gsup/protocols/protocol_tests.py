"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import asyncio
import functools
import unittest
from unittest.mock import Mock

from osmocom.gsup.protocols.ipa import OsmoCtrlManager, OsmoIPAServer
from osmocom.osmocom_ctrl import OsmoCtrlClient, CtrlProcessor, MsgIdError, OsmoCtrlError


class IPATests(unittest.TestCase):
    """
    Test class for osmo IPA protocols
    """

    def setUp(self):
        self._ipa = OsmoIPAServer(None)

        # Mock the writes to check responses
        self._writes = Mock()

        def convert_memview_to_bytes(memview):
            """ Deep copy the memoryview for checking later  """
            return self._writes(memview.tobytes())

        self._transport = asyncio.Transport()
        self._transport.write = Mock(side_effect=convert_memview_to_bytes)

        # Here goes nothing..
        self._ipa.connection_made(self._transport)

    def _check_reply(self, req_bytes, resp_bytes):
        """
        Send data to the protocol in different step lengths to
        verify that we assemble all segments and parse correctly.

        Args:
            req_bytes (bytes): request which would be sent
                multiple times with different step sizes
            resp_bytes (bytes): response which needs to be
                received each time
        Returns:
            None
        """
        for step in range(1, len(req_bytes) + 1):
            offset = 0
            while offset < len(req_bytes):
                self._ipa.data_received(req_bytes[offset:offset + step])
                offset += step
            self._writes.assert_called_once_with(resp_bytes)
            self._writes.reset_mock()

    def _check_ping(self):
        """ Assert if a Ping is received for a Ping message """
        self._check_reply(b'\x00\x01\xfe\x00', b'\x00\x01\xfe\x01')

    def test_ping(self):
        """
        Test if Pong is returned for a Ping message
        """
        self._check_ping()

    def test_ignore_unknown(self):
        """
        Test if an unknown message is ignored
        """
        self._ipa.data_received(b'\x00\x02\xee\x06\x01')
        self._writes.assert_not_called()
        # Check that we still get Pong when Ping is sent
        self._check_ping()

    def test_bad_header(self):
        """
        Test a packet with fake/bad header gets caught.
        """
        self.length = 30
        self.stream_id = 'bad_id'
        self.payload = memoryview(b'\x00\x00\x00\x00')
        self.assertRaises(RuntimeError, self._ipa._handle_ipa_msg,
                          self.length, self.stream_id, self.payload)


class OsmoCtrlClientTests(unittest.TestCase):
    """
    Test class specific to osmo IPA client protocols
    """

    def setUp(self):
        self.mock = Mock()
        self.mock.message = 'message'
        self._client_completed = asyncio.Future()
        self._ctrl_client = functools.partial(OsmoCtrlClient, self.mock.message,
                                              future=self._client_completed)

    def test_client_completed(self):
        """ test connection_lost() completes the client"""
        self.assertEquals(self._client_completed.done(), False)
        self._ctrl_client().connection_lost(None)
        self.assertEquals(self._client_completed.done(), True)


class CtrlProcessorTests(unittest.TestCase):
    """
    Test class for Osmo CTRL processor
    """
    def setUp(self):
        self.request_id = 12345
        self._ctrl_processor = CtrlProcessor(self.request_id)

    def test_bad_request_id(self):
        """ testing mismatch between request/response ids"""
        response = {'id': 11111}
        self.assertRaises(MsgIdError, self._ctrl_processor.process_response, response)

    def test_handle_error_response(self):
        """ testing handling of error message from Osmo stack"""
        response = {'id': self.request_id,
                    'msg_type': "ERROR",
                    'error': b'Read Only attribute'}
        self.assertRaises(OsmoCtrlError, self._ctrl_processor.process_response, response)


class OsmoCtrlManagerTests(unittest.TestCase):
    """
    Test class for Osmo CTRL manager
    """

    def setUp(self):
        self.mock = Mock()
        self._ctrl_manager = OsmoCtrlManager(self.mock.ipa_writer)

    def test_generate_msg_set(self):
        """ testing the generation of a Ctrl SET message"""
        self.mock.variable = 'mcc'
        self.mock.value = 600
        _, self.cmd = self._ctrl_manager.generate_msg(self.mock.variable,
                                                      self.mock.value)
        responses = self._process_msg(self.cmd)
        self.assertEquals(responses['action'], 'SET')
        self.assertEquals(responses['value'], '600')
        self.assertEquals(responses['var'], 'mcc')

    def test_generate_msg_get(self):
        """ testing the generation of a Ctrl GET message"""
        self.mock.variable = 'mcc'
        self.mock.value = None
        _, self.cmd = self._ctrl_manager.generate_msg(self.mock.variable,
                                                      self.mock.value)
        responses = self._process_msg(self.cmd)
        self.assertEquals(responses['action'], 'GET')
        self.assertEquals(responses['value'], None)
        self.assertEquals(responses['var'], 'mcc')

    @staticmethod
    def _process_msg(data):
        """returns the contents of an IPA Osmo Ctrl command as dict of str's"""
        (action, msg_id, msg) = data.split(None, 2)
        msg_id = int(msg_id)
        response = {'action': action, 'id': msg_id}
        if action == "ERROR":
            response['error'] = msg
        else:
            split = msg.split(None, 1)
            response['var'] = split[0]
            if len(split) > 1:
                response['value'] = split[1]
            else:
                response['value'] = None
        return response

if __name__ == "__main__":
    unittest.main()
