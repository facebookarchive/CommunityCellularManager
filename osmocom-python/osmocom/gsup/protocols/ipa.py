"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import asyncio
import logging
import struct

from . import gsup


# IPA constants
IPA_HEADER_LEN = 3
IPA_STREAM_CCM = 0xfe
IPA_STREAM_OSMO = 0xee

# IPA OSMO Extenstions
IPA_OSMO_GSUP = 0x05
IPA_OSMO_OAP = 0x06

# IPA CCM messages
IPA_CCM_PING = 0x00
IPA_CCM_PONG = 0x01


class OsmoIPAccessProtocol(asyncio.Protocol):

    """
    IP Access is layer is used above TCP/IP to:
    - multiplex multiple protocols over the same connection
    - abstract segmentation so higher protocols can handle msg as a whole

    IPA multiplexing layer:

    Offset      Length      Field
    ------      ------      -----
    0           2           Payload length
    2           1           Stream Id (0xfe - CCM, 0xee - OSMO, etc.)
    3           variable    Payload

    OSMO extentions:

    Offset      Length      Field
    ------      ------      -----
    0           1           Protocol (5 - GSUP, 6 - OAP)
    2           variable    Payload

    """

    def __init__(self, gsm_processor):
        self._gsm_processor = gsm_processor
        self._gsup_manager = None
        self._ccm_manager = None
        # bytesarray is more efficient to append fragments of reads
        self._readbuf = bytearray()

    def connection_made(self, transport):
        """
        Handle the new IPA connection.

        Args:
            transport (asynio.Transport): the transport for the new connection
        Returns:
            None
        """
        logging.info("Connection received!")

        writer = IPAWriter(transport, IPA_STREAM_OSMO, IPA_OSMO_GSUP)
        self._gsup_manager = gsup.GSUPManager(self._gsm_processor, writer)

        writer = IPAWriter(transport, IPA_STREAM_CCM)
        self._ccm_manager = IPAConnectionManager(writer)

    def data_received(self, data):
        """
        Append the 'data' bytes to the readbuf, and parse the message
        if the entire message has been received.
        Unparsed bytes will be left in readbuf and will be parsed when
        more data is received in the future.

        Args:
            data (bytes): new data read from the transport
        Returns:
            None
        """
        logging.debug("Bytes read: %s", data)
        self._readbuf.extend(data)

        # Use memoryview to prevent copies when slicing
        memview = memoryview(self._readbuf)
        remain = len(memview)
        begin = 0  # beginning of message

        while remain >= IPA_HEADER_LEN:
            # Parse the header
            (payload_len, stream) = struct.unpack_from('!HB', memview, begin)
            msg_len = IPA_HEADER_LEN + payload_len
            if remain < msg_len:
                # Need more data for the payload
                return

            # Handle the IPA message
            payload = memview[begin + IPA_HEADER_LEN:begin + msg_len]
            try:
                self._handle_ipa_msg(payload_len, stream, payload)
            except Exception as exc:  # pylint: disable=broad-except
                # Handle any exceptions with message handling, without
                # affecting other messages/users
                logging.exception(exc)

            # Get ready for the next message
            begin += msg_len
            remain -= msg_len

        # Get the unparsed bytes
        self._readbuf = bytearray(memview[begin:])

    def connection_lost(self, exc):
        """
        The IPA connection has been lost.

        Args:
            exc: exception object or None if EOF
        Returns:
            None
        """
        logging.warning("Connection lost!")
        self._gsup_manager = None
        self._ccm_manager = None

    def _handle_ipa_msg(self, length, stream_id, payload):
        """
        Handle the payload of an IPA message. This would be
        called after a full IPA message is received.

        Args:
            length (int): length of the payload
            stream_id (int): IPA stream id
            payload (bytes): the underlying message
        Returns:
            None
        """
        if stream_id == IPA_STREAM_CCM:  # IPA Connection Management
            self._ccm_manager.handle_msg(payload)
            return
        elif stream_id == IPA_STREAM_OSMO:  # Osmo extensions
            if payload[0] == IPA_OSMO_GSUP:  # GSUP msgs
                self._gsup_manager.handle_msg(payload[1:])
                return
            elif payload[0] == IPA_OSMO_OAP:  # OAP msgs
                logging.debug("OAP message received")
                return

        logging.warning("Unhandled IPA msg: length: %d, stream_id: %d, "
                        "payload: %s", length, stream_id,
                        payload.decode("utf-8"))


class IPAWriter:

    """
    IPAWriter prepends the appropriate IPA header for higher layer protocols.
    The writer is inited with specific header elements (stream id, etc.)
    """

    def __init__(self, transport, stream_id, osmo_extn=None):
        self._transport = transport
        self._stream_id = stream_id
        self._osmo_extn = osmo_extn
        self._header_len = IPA_HEADER_LEN
        if self._osmo_extn:  # occupies one more byte
            self._header_len += 1

    def get_write_buf(self, length):
        """
        Allocates one chunk of memory for the entire message including
        the header which needs to be prepended. This avoids extra allocations
        and copying.

        Args:
            length (int): length of the protocl message encapsulated by IPA
        Returns:
            memoryview: Allocated buf of header + length bytes.
        """
        buf = memoryview(bytearray(length + self._header_len))
        self.reset_length(buf, length)
        return buf, self._header_len

    def reset_length(self, buf, length):
        """
        Writes an IPA header with the length param. Used externally when
        protocols over provision memory initially and then reset the length.

        Args:
            buf (memoryview): the IPA message
            length (int): length of the protocl message encapsulated by IPA
        Returns:
            None
        """
        if self._osmo_extn:
            struct.pack_into('!HBB', buf, 0, length + 1,
                             self._stream_id, self._osmo_extn)
        else:
            struct.pack_into('!HB', buf, 0, length, self._stream_id)

    def write(self, buf):
        """ Write the buffer to the underlying socket """
        self._transport.write(buf)


class IPAConnectionManager:

    """
    Class to perform connection management operations.
    We might need to run a timer and proactively perform Pings if needed.

    IPA CCM (Connection Management):

    Offset      Length      Field
    ------      ------      -----
    0           1           Purpose (0 - ping, 1 - pong, etc.)
    """

    def __init__(self, ipa_writer):
        self._ipa_writer = ipa_writer

    def handle_msg(self, msg):
        """
        Handle the CCM messages. We are only interested in Pings from peers.

        Args:
            msg (bytes): full IPA CCM message
        Returns:
            None
        """
        if msg[0] == IPA_CCM_PING:
            logging.info("Ping message received. Sending back Pong")
            self.send_pong()
        else:
            logging.debug("Unknown message received: %d", msg[0])

    def send_pong(self):
        """
        Send the Pong message to the peer.

        Returns:
            None
        """
        (buf, offset) = self._ipa_writer.get_write_buf(1)
        buf[offset] = IPA_CCM_PONG
        self._ipa_writer.write(buf)
