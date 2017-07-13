"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import asyncio
import logging
import random
import struct
from abc import ABC, abstractmethod

from . import gsup


# IPA Constants
# References:
# - http://ftp.osmocom.org/docs/latest/osmobts-abis.pdf
# - http://ftp.osmocom.org/docs/latest/osmobsc-usermanual.pdf

# IPA Misc
IPA_HEADER_LEN = 3

# IPA Stream ID
IPA_STREAM_CCM = 0xfe
IPA_STREAM_OSMO = 0xee

# IPA Osmo Extenstions
IPA_OSMO_GSUP = 0x05
IPA_OSMO_OAP = 0x06
IPA_OSMO_CTRL = 0x00

# IPA CCM messages
IPA_CCM_PING = 0x00
IPA_CCM_PONG = 0x01

# IPA ports
TCP_PORT_OML = 3002
TCP_PORT_RSL = 3003
TCP_PORT_NITB = 4249

# IPA cmds
GET_CMD = 'GET'
SET_CMD = 'SET'
TRAP_CMD = 'TRAP'


class OsmoIPAccessProtocol(asyncio.Protocol, ABC):

    """
    IP Access is layer is used above TCP/IP to:
    - multiplex multiple protocols over the same connection
    - abstract segmentation so higher protocols can handle msg as a whole

    References:
    - http://ftp.osmocom.org/docs/latest/osmobts-abis.pdf

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

    def __init__(self, gsup_callback=None, ctrl_callback=None):
        self._gsup_callback = gsup_callback
        self._ctrl_callback = ctrl_callback
        self._readbuf = bytearray()

    def connection_made(self, transport):
        """
        Serves to initialize all protocol managers and their writers with each
        protocol's respective headers.

        In the case of server subclasses, this connection_made() may
        be sufficent, while the server waits for data to be received.

        However most client subclasses, further functionality will generally be
        required in their connection_made() to transmit client message.
        """
        logging.info("Connection made!")

        writer = IPAWriter(transport, IPA_STREAM_OSMO, IPA_OSMO_GSUP)
        self._gsup_manager = gsup.GSUPManager(self._gsup_callback, writer)

        writer = IPAWriter(transport, IPA_STREAM_CCM)
        self._ccm_manager = IPAConnectionManager(writer)

        writer = IPAWriter(transport, IPA_STREAM_OSMO, IPA_OSMO_CTRL)
        self._ctrl_manager = OsmoCtrlManager(self._ctrl_callback, writer)

    def data_received(self, data):
        """
        Append the 'data' bytes to the readbuf, and parse the message
        if the entire message has been received.
        Unparsed bytes will be left in readbuf and will be parsed when
        more data is received in the future.

        Strips away outer headers of the IPA packet:
        - payload length
        - IPA Stream ID
        - converts remainder of packet into a memoryview object

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
            (payload_len, ipa_stream_id) = struct.unpack_from('!HB', memview, begin)
            msg_len = IPA_HEADER_LEN + payload_len
            if remain < msg_len:
                # Need more data for the payload
                return

            # Handle the IPA message
            payload = memview[(begin + IPA_HEADER_LEN):(begin + msg_len)]
            try:
                self._handle_ipa_msg(payload_len, ipa_stream_id, payload)

            except Exception as exc:  # pylint: disable=broad-except
                # Handle any exceptions with message handling, without
                # affecting other messages/users
                logging.exception(exc)

            # Get ready for the next message
            begin += msg_len
            remain -= msg_len

        # Get the unparsed bytes
        self._readbuf = bytearray(memview[begin:])

    @abstractmethod
    def connection_lost(self, exc):
        """
        The IPA connection has been lost.

        Args:
            exc: exception object or None if EOF
        Returns:
            None
        """
        if exc:
            logging.warning("Connection lost, Exception: {}".format(exc))
        else:
            logging.info("Closing connection")


    def _handle_ipa_msg(self, length, stream_id, payload):
        """
        Handle the payload of an IPA message, strips away a header
        and sends the remainder of the packet to the respective manager:
        based the IPA Stream ID, and IPA Osmo Extenstions where appropriate.

        This would be called after a full IPA message is received.

        Strips away  headers of the IPA packet:
        - IPA Osmo extension

        Args:
            length (int): length of the payload
            stream_id (int): IPA stream id
            payload (memoryview): the underlying message
        Returns:
            None
        """
        if stream_id == IPA_STREAM_CCM and self._ccm_manager is not None:
            self._ccm_manager.handle_msg(payload)
            return
        elif stream_id == IPA_STREAM_OSMO:
            if payload[0] == IPA_OSMO_GSUP and self._gsup_manager is not None:
                self._gsup_manager.handle_msg(payload[1:])
                return
            elif payload[0] == IPA_OSMO_OAP:
                logging.debug("OAP message received")
                return
            elif payload[0] == IPA_OSMO_CTRL and self._ctrl_manager is not None:
                self._ctrl_manager.handle_msg(payload[1:])
                return

        raise RuntimeError("Unhandled IPA msg: length: %d, stream_id: %d, "
                           "payload: %s", length, stream_id,
                           bytearray(payload).decode("utf-8"))


class OsmoIPAServer(OsmoIPAccessProtocol):

    """
    Handle the new IPA connection as a server.

    Currently server supports GSUP, and CCM protocols.

    Two steps are required to start the server, first use the event loop to create
    a new server object using this protocol class and hostname / socket to listen on.
    Because create_server() returns a coroutine (generator in case of python 3.4),
    the OsmoIPAServer process will begin only after the loop is started on the coroutine
    with a command like: `run_until_complete`

    An example of this is in `osmocom_hlr`:
    ```
    loop = asyncio.get_event_loop()

    ipa_server = functools.partial(OsmoIPAServer, processor)
    server_coro = loop.create_server(ipa_server, '0.0.0.0', 2222)
    server = loop.run_until_complete(server_coro)
    ````
    """
    def __init__(self, gsup_callback=None):
        super().__init__(gsup_callback=gsup_callback)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        self._gsup_manager = None
        self._ccm_manager = None


class OsmoIPAClient(OsmoIPAccessProtocol):

    """
    Handle the new IPA connection as a client.

    Two steps are required to start the client, first use the event loop to create
    a new connection object using this protocol class and hostname / socket to send to,
    as well as the message to send.

    Because create_connection() returns a coroutine (generator in case of python 3.4),
    the OsmoIPAClient process will begin only after the loop is started on the coroutine
    with a command like: `run_until_complete`

    An example of this is in `osmocom_ctrl`:


    ```
    loop = asyncio.get_event_loop()
    ...
    ctrl_client = functools.partial(OsmoCtrlClient, msg, callback)
    client_coro = loop.create_connection(ctrl_client, HOST, PORT)

    try:
        _, protocol = loop.run_until_complete(client_coro)
    finally:
        protocol.connection_lost(exc=None)
    ````
    """

    def __init__(self, ctrl_callback=None):
        super().__init__(ctrl_callback=ctrl_callback)

    def connection_lost(self, exc):
        super().connection_lost(exc)
        self._ctrl_manager = None


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
        if self._osmo_extn is not None:  # occupies one more byte
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
        if self._osmo_extn is not None:  # Ctrl extn is 0x00
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

    Reference:
    - http://ftp.osmocom.org/docs/latest/osmobts-abis.pdf

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


class OsmoCtrlManager:

    """
    Class to perform management for the CTRL interface (which is
    exposed at the various layers of the Osmocom GSM stack).

    References:
    - http://ftp.osmocom.org/docs/latest/*-usermanual.pdf
    i.e.
    - http://ftp.osmocom.org/docs/latest/osmobsc-usermanual.pdf

    An example CTRL packets look at follows:
    b'\x00\x0e\xee\x00SET 14686 mnc 2

    - x00\x0e   : payload length
    - xee       : IPA_STREAM_OSMO header
    - x00       : IPA_OSMO_CTRL header extension
    - SET       : GET, SET or TRAP command
    - 14686     : unique message ID
    - mnc       : variable being set
    - 2         : value variable is being set to
    """

    def __init__(self, ctrl_callback=None, ipa_writer=None):
        self._ipa_writer = ipa_writer
        self._ctrl_callback = ctrl_callback

    def handle_msg(self, payload):
        """
        Handle the Ctrl messages.

        Args:
            payload (memoryview): payload of IPA Ctrl message
                        - packet minus IPA Straem ID and Osmo extension headers
            request_id (int): random id that was associated client's request

        Returns:
            None

        Prints:
            response (dict): variable value pairs from contents of the msg
        """
        (msg_type, msg_id, msg) = bytearray(payload).split(None, 2)
        msg_id = int(msg_id)
        response = {'msg_type': msg_type.decode('utf-8'), 'id': msg_id}
        if response['msg_type'] == "ERROR":
            response['error'] = msg.decode('utf-8')

        else:
            split = msg.split(None, 1)
            response['var'] = split[0].decode('utf-8')
            if len(split) > 1:
                response['val'] = split[1].decode('utf-8')
            else:
                response['val'] = None

        self._ctrl_callback.process_response(response)

    @staticmethod
    def generate_msg(var, val=None):
        """
        Generate SET/GET command message: returns (msg_id, cmd).
        """
        msg_id = random.randint(10000, 20000)
        if val is not None:
            return msg_id, "%s %s %s %s" % (SET_CMD, msg_id, var, val)
        return msg_id, "%s %s %s" % (GET_CMD, msg_id, var)

    def generate_packet(self, message):
        """
        Encodes and sends the message to the IPA layer.
        """
        buf_size = len(message)
        # offset accounts for header_len
        (buf, offset) = self._ipa_writer.get_write_buf(buf_size)

        msg_byte_list = memoryview(bytearray(message.encode('utf-8'))).tolist()
        for i, byte in enumerate(msg_byte_list):
            buf[offset+i] = byte

        # Write the encoded msg
        self._ipa_writer.write(buf)
