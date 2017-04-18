"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

from unittest.mock import Mock

from osmocom.gsup.crypto.utils import CryptoError
from osmocom.gsup.processor import GSMProcessor
from osmocom.gsup.protocols.gsup import \
    GPRSSubcriberUpdateProtocol, GSUPManager
from osmocom.gsup.protocols.gsup import \
    MsgType, IEType, ErrorCauseType, GSUPCodecError
from osmocom.gsup.protocols.ipa import IPAWriter
from osmocom.gsup.store.base import SubscriberNotFoundError


def _dummy_auth_tuple():
    rand = b'ni\x89\xbel\xeeqTT7p\xae\x80\xb1\xef\r'
    sres = b'\xd4\xac\x8bS'
    key = b'\x9f\xf54.\xb9]\x88\x00'
    return (rand, sres, key)


class CodecTests(unittest.TestCase):
    """
    Tests for the GSUP encoder/decoder
    """

    def setUp(self):
        self._gsup = GPRSSubcriberUpdateProtocol()

    def _decode_check(self, msg_type, msg_ies, msg_bytes):
        (out_type, out_ies) = self._gsup.decode(memoryview(msg_bytes))
        self.assertEqual(out_type, msg_type)
        self.assertEqual(out_ies, msg_ies)

    def _encode_check(self, msg_type, msg_ies, msg_bytes):
        out_buf = bytearray(len(msg_bytes))
        out_len = self._gsup.encode(out_buf, 0, msg_type, msg_ies)
        self.assertGreater(out_len, 0)
        self.assertEqual(out_buf, msg_bytes)

    def _compare_msg(self, msg_type, msg_ies, msg_bytes):
        # Test decoder
        self._decode_check(msg_type, msg_ies, msg_bytes)

        # Test encoder
        self._encode_check(msg_type, msg_ies, msg_bytes)

    def test_valid_messages(self):
        """
        Test if valid messages are encoded and decoded correctly
        """
        self._compare_msg(
            MsgType.SEND_AUTH_INFO_REQ,
            {
                IEType.CN_DOMAIN: 1,
                IEType.IMSI: '001555000001276',
            },
            b'\x08\x28\x01\x01\x01\x08\x00\x51\x55\x00\x00\x10\x72\xf6')
        self._compare_msg(
            MsgType.SEND_AUTH_INFO_ERR,
            {
                IEType.IMSI: '001555000001276',
                IEType.CAUSE: ErrorCauseType.PROTOCOL_ERR,
            },
            b'\x09\x01\x08\x00\x51\x55\x00\x00\x10\x72\xf6\x02\x01\x6f')
        self._compare_msg(
            MsgType.SEND_AUTH_INFO_RSP,
            {
                IEType.IMSI: '00155',
                IEType.AUTH_TUPLE: _dummy_auth_tuple(),
            },
            b'\n\x01\x03\x00Q\xf5\x03" \x10ni\x89\xbel\xeeqTT7p\xae\x80\xb1' +
            b'\xef\r!\x04\xd4\xac\x8bS"\x08\x9f\xf54.\xb9]\x88\x00')
        self._compare_msg(
            MsgType.UPDATE_LOCATION_REQ,
            {
                # Optional IEType.CN_DOMAIN
                IEType.IMSI: '00155',  # odd numbered IMSI
            },
            b'\x04\x01\x03\x00\x51\xf5')

    def test_encoding_missing_ies(self):
        """
        Mandatory IMSI IE missing
        """
        out_buf = bytearray(100)
        with self.assertRaises(GSUPCodecError):
            self._gsup.encode(out_buf, 0, MsgType.SEND_AUTH_INFO_REQ, {})

    def test_encoding_bad_imsi(self):
        """
        Test if we can handle encoding invalid IMSIs
        """
        out_buf = bytearray(100)
        # String IMSI
        with self.assertRaises(GSUPCodecError):
            self._gsup.encode(
                out_buf, 0, MsgType.SEND_AUTH_INFO_REQ,
                {IEType.IMSI: 'asd'})

        # Really really long IMSI
        with self.assertRaises(GSUPCodecError):
            self._gsup.encode(
                out_buf, 0, MsgType.SEND_AUTH_INFO_REQ,
                {IEType.IMSI: '123456789123456789123456789'})

    def test_encoding_bad_auth_tuple(self):
        """
        Invalid Auth Tuple (rand not 16 bytes)
        """
        out_buf = bytearray(100)
        (_, sres, key) = _dummy_auth_tuple()
        with self.assertRaises(GSUPCodecError):
            self._gsup.encode(
                out_buf, 0, MsgType.SEND_AUTH_INFO_RSP,
                {
                    IEType.IMSI: '00155',
                    IEType.AUTH_TUPLE: (b'\x01', sres, key)
                })

    def test_decoding_unknown_msg(self):
        """
        Zero length message or unknown message type
        """
        # Zero length message
        with self.assertRaises(GSUPCodecError):
            self._gsup.decode(memoryview(b''))

        # Unknown message type 0x01
        with self.assertRaises(GSUPCodecError):
            self._gsup.decode(memoryview(b'\x01'))

    def test_decoding_invalid_ies(self):
        """
        Test if we can handle decoding bad IEs
        """
        # IMSI IE missing
        with self.assertRaises(GSUPCodecError):
            self._gsup.decode(memoryview(b'\x08\x02\x01\x01'))

        # unknown IE
        self._decode_check(
            MsgType.SEND_AUTH_INFO_REQ,
            {
                IEType.IMSI: '001555000001276',
            },
            b'\x08\x00\x01\x01\x01\x08\x00\x51\x55\x00\x00\x10\x72\xf6')

        # IE bytes missing
        with self.assertRaises(GSUPCodecError):
            self._gsup.decode(memoryview(b'\x08\x02\x01'))

        # Cause IE having length 2 bytes instead of 1
        with self.assertRaises(GSUPCodecError):
            self._gsup.decode(memoryview(b'\x08\x02\x02\x01\x01'))


class MockProcessor(GSMProcessor):

    def get_gsm_auth_vector(self, imsi):
        if imsi == '1':
            return _dummy_auth_tuple()
        elif imsi == '2':
            raise CryptoError
        else:
            raise SubscriberNotFoundError


class ManagerTests(unittest.TestCase):
    """
    Tests for the GSUP Manager
    """

    def setUp(self):
        self._gsup = GPRSSubcriberUpdateProtocol()

        # Queue the messages to check later
        self._out_msgs = Mock()

        def queue_message(memview):
            """ Decode and queue GSUP msg """
            (msg_type, ies) = self._gsup.decode(memview[3:])
            return self._out_msgs(msg_type, ies)

        writer = IPAWriter(None, 0x01)
        writer.write = Mock(side_effect=queue_message)

        self._manager = GSUPManager(MockProcessor(), writer)

    def _input_msg(self, msg_type, ies):
        """
        Encode and input the message to the manager.
        """
        buf = memoryview(bytearray(100))
        out_len = self._gsup.encode(buf, 0, msg_type, ies)
        self.assertGreater(out_len, 0)
        self._manager.handle_msg(buf[:out_len])

    def test_auth_imsi_unknown(self):
        """
        Test if we get IMSI_UNKNOWN error for Auth req for random IMSIs
        """
        self._input_msg(
            MsgType.SEND_AUTH_INFO_REQ,
            {
                IEType.IMSI: '123',
            })
        self._out_msgs.assert_called_once_with(
            MsgType.SEND_AUTH_INFO_ERR,
            {
                IEType.IMSI: '123',
                IEType.CAUSE: ErrorCauseType.IMSI_UNKNOWN,
            })

    def test_auth_key_missing(self):
        """
        Test if we get NETWORK_FAILURE error for Auth req if crypto fails
        """
        self._input_msg(
            MsgType.SEND_AUTH_INFO_REQ,
            {
                IEType.IMSI: '2',
            })
        self._out_msgs.assert_called_once_with(
            MsgType.SEND_AUTH_INFO_ERR,
            {
                IEType.IMSI: '2',
                IEType.CAUSE: ErrorCauseType.NETWORK_FAILURE,
            })

    def test_auth_success(self):
        """
        Test if we send the Auth Tuple for valid IMSIs
        """
        self._input_msg(
            MsgType.SEND_AUTH_INFO_REQ,
            {
                IEType.IMSI: '1',
            })
        self._out_msgs.assert_called_once_with(
            MsgType.SEND_AUTH_INFO_RSP,
            {
                IEType.IMSI: '1',
                IEType.AUTH_TUPLE: _dummy_auth_tuple(),
            })

    def test_update_location(self):
        """
        Test if we send INSERT_SUBS_DATA_REQ with the * APN
        """
        self._input_msg(
            MsgType.UPDATE_LOCATION_REQ,
            {
                IEType.IMSI: '1',
            })
        self._out_msgs.assert_called_once_with(
            MsgType.INSERT_SUBS_DATA_REQ,
            {
                IEType.IMSI: '1',
                IEType.PDP_INFO_COMPLETE: bytes(),
                IEType.PDP_INFO: b'\x10\x01\x01\x11\x02\x01!\x12\x02\x01*',
            })
        self._out_msgs.reset_mock()
        self._input_msg(
            MsgType.INSERT_SUBS_DATA_RES,
            {
                IEType.IMSI: '1',
            })
        self._out_msgs.assert_called_once_with(
            MsgType.UPDATE_LOCATION_RES,
            {
                IEType.IMSI: '1',
            })

if __name__ == "__main__":
    unittest.main()
