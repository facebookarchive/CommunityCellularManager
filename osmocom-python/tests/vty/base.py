"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import unittest

import mock

import osmocom.vty.base

class MockSocketTestCase(unittest.TestCase):
    fixture_file = ''

    @classmethod
    def setUpClass(cls):
        cls.original_socket = osmocom.vty.base.socket
        cls.mock_socket = mock.MagicMock()
        osmocom.vty.base.socket.socket = mock.Mock()
        osmocom.vty.base.socket.socket.return_value = cls.mock_socket

        # We mock socket.recv to read one line from a text file defined for the class
        f = open(cls.fixture_file, encoding='UTF-8', errors='ignore')
        recv_fixture_buffer = f.readlines()

        def recv_fixture(_):
            if len(recv_fixture_buffer):
               return bytearray(recv_fixture_buffer.pop(0)[:-1] + '\r\n', 'utf-8')
            return b''

        cls.mock_socket.recv = recv_fixture

        # We also need to mock the check the recv loop uses to see if there more to read
        osmocom.vty.base.select = mock.Mock()
        osmocom.vty.base.select.select = lambda rlist, wlist, xlist, timeout=None: \
            (rlist, [], []) if len(recv_fixture_buffer) > 0 else ([], [], [])

    @classmethod
    def tearDownClass(cls):
        osmocom.vty.base.socket = cls.original_socket

    def setUp(self):
        # We mock socket.sendall to capture what is sent to the tty
        self.sendall_buffer = ''
        def sendall_fixture(msg):
          self.sendall_buffer += msg.decode('utf-8') + '\n'
        self.mock_socket.sendall = sendall_fixture
