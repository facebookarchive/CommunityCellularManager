"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import asyncio
import unittest

from unittest.mock import Mock

from osmocom.gsup.protocols.ipa import OsmoIPAccessProtocol


class IPATests(unittest.TestCase):
    """
    Test class for osmo IPA protocols
    """

    def setUp(self):
        self._ipa = OsmoIPAccessProtocol(None)

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


if __name__ == "__main__":
    unittest.main()
