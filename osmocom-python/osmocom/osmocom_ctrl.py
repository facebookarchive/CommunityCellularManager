#!/usr/bin/env python3
"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import argparse
import asyncio
import functools
import logging
import sys
import warnings

from .gsup.protocols.ipa import OsmoIPAClient, OsmoCtrlManager


# IPA Constants and References
# References:
# - http://ftp.osmocom.org/docs/latest/osmobts-abis.pdf
# - http://ftp.osmocom.org/docs/latest/osmobsc-usermanual.pdf

# IPA ports
TCP_PORT_NITB = 4249

# Script globals
HOST = '127.0.0.1'
PORT = TCP_PORT_NITB
SERVER_ADDRESS = (HOST, PORT)


def main():
    """
    `osmocom_ctrl.py` expose the new Osmocom Ctrl interface to SET/GET state
    on an actively running instance of the Osmocom GSM stack. This can be used
    instead of the VTY interface for programatic access to config.

    Reccomended usage (access to help menu with further details)
    in `osmocom-python` call `PYTHONASYNCIODEBUG=1 python3 -m osmocom.osmocom_ctrl -h`

    Open: Plan for how to pass on results. Currently response is returned to main
    function
    """
    logging.basicConfig(format='%(asctime)s  %(levelname)s: %(message)s',
                        stream=sys.stdout, level=logging.DEBUG)
    # Report all mistakes managing asynchronous resources.
    warnings.simplefilter('always', ResourceWarning)

    args = parse_args()
    if args.set:
        var, value = args.set
    if args.get:
        var, = args.get
        value = None

    if args.trap:
        var = value = msg = msg_id = None

    output = open(args.outfile, 'w+') if args.outfile else sys.stdout

    # Initialize event loop.
    loop = asyncio.get_event_loop()

    # Use OsmoCtrlManager's methods to generate msg and msg_id for GET/SET requests
    if not args.trap:
        (msg_id, msg) = OsmoCtrlManager.generate_msg(var, value)

    # CtrlProcessor callback instance called by the OsmoCtrlClient (via OsmoCtrlManager)
    processor_cb = CtrlProcessor(msg_id)

    # Future instance to use to signal that the client is done
    client_completed = asyncio.Future()

    # Wrapping protocol class because event loop can notaccept extra arguments.
    ctrl_client = functools.partial(OsmoCtrlClient, msg,
                                    future=client_completed,
                                    callback=processor_cb)

    # Protocol class, msg, future, and callback passed to the event loop to create
    # the connection.
    client_coro = loop.create_connection(ctrl_client, HOST, PORT)

    logging.info('waiting for client to complete')
    try:
        # Event loop called once for initiating the OsmoCtrlClient protocol
        loop.run_until_complete(client_coro)

        # Display response from GET/SET request or from TRAP
        response = processor_cb.response
        print('\nResponse for {} request, var: {}, val: {}\n'.format(response['msg_type'],
              response['var'], response['val']), file=output)

        # Called again to run until the protocol defined by OsmoCtrlClient has completed
        loop.run_until_complete(client_completed)

    finally:
        logging.debug('closing from main()')
        loop.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description='Access to GET/SET/TRAP variables in running osmocom GSM stack through CLI.\
        Refer to manual for exposed variables: \
        http://ftp.osmocom.org/docs/latest/*-usermanual.pdf, \
        i.e. http://ftp.osmocom.org/docs/latest/osmobsc-usermanual.pdf')
    parser.add_argument(
        "-s", "--set",
        nargs=2,
        default=None,
        help="SET <var> <val>")
    parser.add_argument(
        "-g", "--get",
        nargs=1,
        default=None,
        help="GET <var>")
    parser.add_argument(
        "-t", "--trap",
        action='store_true',
        default=False,
        help="TRAP")
    parser.add_argument(
        "-o", "--outfile",
        type=str,
        default=None,
        help="outfile <filename>")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    return args


class CtrlProcessor:

    """
    Interface for the CTRL protocol to interact with other parts of CCM.

    Curren: only deals with errors.

    Open:
    - add interface such as gRPC for interaction with other CCM components.
    """

    def __init__(self, msg_id):
        self.request_id = msg_id

    def process_response(self, response):
        """ Interface to application layer processing of Osmo CTRL responses"""
        self.response = response  # enabling callback access to attribute
        if self.request_id == response['id']:
            if response['msg_type'] == "ERROR":
                raise OsmoCtrlError('Request id: {}, returned error response: {}'.
                                    format(response['id'], response['error']))
        else:
            raise MsgIdError('Mismatch between response message id: {} \
                            and request message id: {}.'\
                            .format(response['id'], self.request_id))


class OsmoCtrlClient(OsmoIPAClient):
    """
    Ctrl ports:
    L4 protocol   |Port Number|   Purpose              |    Software
    ----------------------------------------------------------------------------
    TCP           |   4249    |   Control interface    |    osmo-nitb, osmo-bsc
    TCP           |   4250    |   Control interface    |    osmo-bsc_nat
    TCP           |   4251    |   Control interface    |    osmo-sgsn
    TCP           |   4255    |   Control interface    |    osmo-msc
    TCP           |   4257    |   Control interface    |    ggsn (OpenGGSN)
    TCP           |   4259    |   Control interface    |    osmo-hlr
    """
    def __init__(self, message, future, callback=None):
        super().__init__(ctrl_callback=callback)
        self.future = future
        self.message = message
        self.trap = not bool(self.message)  # TRAP request have no message

    def connection_made(self, transport):
        """
        Establish the new IPA connection as a client

        Args:
            transport (asynio.Transport): the transport for the new connection
        Returns:
            None
        """
        super().connection_made(transport)
        self.transport = transport
        self.address = self.transport.get_extra_info('peername')
        logging.debug('connecting to {} port {}'.format(*self.address))
        if self.message is not None:
            self._ctrl_manager.generate_packet(self.message)

    def data_received(self, data):
        """
        Close transport as required by protocol

        CTRL protocol doesn't specify an End of File (eof) nor does the
        server necesarily close after communication terminates. TRAP
        communication maintains an open connection, while GET/SET terminate

        Args:
            data (bytes): new data read from the transport
        Returns:
            None
        """
        super().data_received(data)
        if not self.trap:
            self.transport.close()

    def connection_lost(self, exc):
        """
        The IPA connection has been lost.

        Args:
            exc: exception object or None if EOF
        Returns:
            None
        """
        if not self.future.done():
            self.future.set_result(True)
        self._ctrl_manager = None
        super().connection_lost(exc)  # rare case of calling super() after cleaning up locally


class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class MsgIdError(Error):
    """Error when response_id from Osmo stack doesn't match request_id"""
    pass


class OsmoCtrlError(Error):
    """Error message returned from Osmo stack"""
    pass


if __name__ == '__main__':
    main()
