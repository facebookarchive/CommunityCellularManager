"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import osmocom.vty.base

from .base import MockSocketTestCase

from . import get_fixture_path
import json
import unittest
import mock

class RunningConfigTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('running_config.txt')

    def test_running_config(self):
        """Test reading bts settings."""
        with osmocom.vty.base.BaseVTY('OpenBSC') as v:
            data_a = v.running_config()
            data_b = {"network": {
                      "encryption a5": "0",
                      "handover window rxlev neighbor averaging": "10",
                      "handover power budget hysteresis": "3",
                      "handover power budget interval": "6",
                      "timer t3113": "60",
                      "mm info": "1",
                      "long name": "Test_Network",
                      "timer t3117": "0",
                      "timer t3115": "0",
                      "handover": "0",
                      "timer t3119": "0",
                      "short name": "Test",
                      "mobile network code": "55",
                      "subscriber-keep-in-ram": "1",
                      "dtx-used": "0",
                      "handover window rxlev averaging": "10",
                      "handover maximum distance": "9999",
                      "network country code": "901",
                      "timer t3111": "0",
                      "location updating reject cause": "13",
                      "timer t3122": "10",
                      "timer t3141": "0",
                      "timer t3101": "10",
                      "timer t3103": "0",
                      "paging any use tch": "0",
                      "timer t3105": "0",
                      "neci": "1",
                      "rrlp mode": "none",
                      "timer t3109": "0",
                      "timer t3107": "0",
                      "auth policy": "accept-all",
                      "handover window rxqual averaging": "1",
                      "bts": {
                        "0": {
                          "gprs ns timer tns-alive-retries": "10",
                          "gprs nsvc 0 nsvci": "101",
                          "rxlev access min": "0",
                          "gprs ns timer tns-block": "3",
                          "gprs ns timer tns-test": "30",
                          "rach max transmission": "7",
                          "ip.access unit_id 1801": "0",
                          "gprs cell timer capability-update-retries": "3",
                          "force-combined-si": "no",
                          "cell reselection hysteresis": "4",
                          "gprs nsvc 1 local udp port": "0",
                          "gprs nsei": "101",
                          "trx": {
                            "0": {
                              "rf_locked": "0",
                              "nominal power": "23",
                              "rsl e1 tei": {
                                "0": {
                                  "timeslot": {
                                    "1": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "TCH/F"
                                      },
                                    "0": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "CCCH+SDCCH4"
                                      },
                                    "3": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "TCH/F"
                                      },
                                    "2": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "TCH/F"
                                      },
                                    "5": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "PDCH"
                                      },
                                    "4": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "PDCH"
                                      },
                                    "7": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "PDCH"
                                      },
                                    "6": {
                                      "hopping enabled": "0",
                                      "phys_chan_config": "PDCH"
                                      }
                                    }
                                  }
                                },
                              "max_power_red": "0",
                              "arfcn": "885"
                              }
                            },
                          "gprs cell timer resume-timer": "10",
                          "gprs ns timer tns-block-retries": "3",
                          "gprs ns timer tns-reset-retries": "3",
                          "gprs cell timer blocking-timer": "3",
                          "gprs ns timer tns-alive": "3",
                          "gprs nsvc 0 remote ip": "127.0.0.2",
                          "gprs nsvc 1 nsvci": "0",
                          "oml ip.access stream_id 255 line": "0",
                          "type": "sysmobts",
                          "gprs nsvc 1 remote udp port": "0",
                          "base_station_id_code": "61",
                          "gprs cell timer suspend-retries": "3",
                          "channel-descrption bs-ag-blks-res": "1",
                          "radio-link-timeout": "32",
                          "gprs cell timer resume-retries": "3",
                          "neighbor-list mode": "automatic",
                          "periodic location update": "30",
                          "gprs nsvc 0 remote udp port": "23000",
                          "rach tx integer": "9",
                          "band": "DCS1800",
                          "gprs cell timer capability-update-timer": "10",
                          "gprs cell timer reset-retries": "3",
                          "channel-descrption bs-pa-mfrms": "5",
                          "channel-descrption attach": "1",
                          "gprs cell timer suspend-timer": "10",
                          "gprs network-control-order": "nc0",
                          "gprs mode": "gprs",
                          "gprs ns timer tns-reset": "3",
                          "gprs cell bvci": "2",
                          "gprs cell timer blocking-retries": "3",
                          "gprs routing area": "1",
                          "gprs nsvc 0 local udp port": "23000",
                          "codec-support": "fr",
                          "location_area_code": "3",
                          "cell_identity": "1",
                          "ms max power": "12",
                          "gprs cell timer unblocking-retries": "3",
                          "gprs nsvc 1 remote ip": "0.0.0.0",
                          "channel allocator": "descending",
                          "gprs cell timer reset-timer": "3"
                        }
                      },
                    },
                    "mncc-int": {
                        "default-codec tch-h": "hr",
                        "default-codec tch-f": "fr"
                        },
                    "log stderr": {
                        "logging level rll": "notice",
                        "logging level mncc": "notice",
                        "logging level smpp": "debug",
                        "logging level ns": "info",
                        "logging level nm": "info",
                        "logging level ctrl": "notice",
                        "logging level llc": "debug",
                        "logging level filter": "debug",
                        "logging level rr": "notice",
                        "logging level gprs": "debug",
                        "logging level lglobal": "notice",
                        "logging level ref": "notice",
                        "logging level ho": "notice",
                        "logging level llapd": "notice",
                        "logging level linp": "notice",
                        "logging level lctrl": "notice",
                        "logging level bssgp": "debug",
                        "logging level msc": "notice",
                        "logging level all": "everything",
                        "logging level db": "notice",
                        "logging level lgtp": "notice",
                        "logging level pag": "notice",
                        "logging level nat": "notice",
                        "logging timestamp": "1",
                        "logging level meas": "notice",
                        "logging level lsms": "notice",
                        "logging level lmib": "notice",
                        "logging level sndcp": "debug",
                        "logging level mm": "notice",
                        "logging level mgcp": "notice",
                        "logging level rsl": "notice",
                        "logging print category": "0",
                        "logging level lmi": "notice",
                        "logging level lmux": "notice",
                        "logging color": "1",
                        "logging level cc": "notice",
                        "logging level sccp": "notice",
                        "logging level lstats": "notice",
                        "logging filter all": "1"
                        },
                    "smpp": {
                        "policy": "closed",
                        "local-tcp-port": "2775",
                        "esme OSMPP": {
                          "default-route": "",
                          "password": "etagecom"
                          },
                        "smpp-first": "no"
                        },
                    "nitb": {
                        "subscriber-create-on-demand": "",
                        "assign-tmsi": ""
                        },
                    "stats interval": "5",
                    "e1_input": {
                        "e1_line 0 keepalive": "no",
                        "e1_line 0 port": "0",
                        "e1_line 0 driver": "ipa"
                        },
                    "line vty": {
                        "login": "no"
                        }
                    }
        a, b = json.dumps(data_a, sort_keys=True), json.dumps(data_b, sort_keys=True)
        self.assertEqual(a, b)


class NestedContextTestCase(MockSocketTestCase):
    fixture_file = get_fixture_path('running_config.txt')

    @classmethod
    def setUpClass(cls):
       super(NestedContextTestCase, cls).setUpClass()
       cls.vty = osmocom.vty.base.BaseVTY('OpenBSC')

    def test_nested_context(self):
        """Tests that we can share a connection context."""
        self.assertEqual(self.vty._context_depth, 0)
        with self.vty:
            self.assertEqual(self.vty._context_depth, 1)
            with self.vty:
                self.assertEqual(self.vty._context_depth, 2)
            self.assertEqual(self.vty._context_depth, 1)
        self.assertEqual(self.vty._context_depth, 0)

    def test_nested_calls(self):
        """Test that we can make nested function calls that
        share a connection context.
        """
        def foo():
            with self.vty:
                self.assertEqual(self.vty._context_depth, 2)
        self.assertEqual(self.vty._context_depth, 0)
        with self.vty:
            self.assertEqual(self.vty._context_depth, 1)
            foo()
        self.assertEqual(self.vty._context_depth, 0)

class FailedConnectionTestCase(unittest.TestCase):
    """We defined a VTY connection to be in the closed state when self._socket_obj
    is set to None. Therefore, in the case of a socket that has failed, we
    need to ensure that it gets reset to None.
    """
    @classmethod
    def setUpClass(cls):
       super(FailedConnectionTestCase, cls).setUpClass()
       cls.vty = osmocom.vty.base.BaseVTY('OpenBSC')

    def test_open_exceptions(self):
        """Tests that a failed connect attempt keeps the
        socket as None so we can reconnect again."""

        # Starts off "disconnected"
        self.assertEqual(self.vty._socket_obj, None)

        # Connection with context manager will fail
        with self.assertRaises(osmocom.vty.exceptions.VTYChainedException):
            with self.vty:
                pass
        # Still "disconnected"
        self.assertEqual(self.vty._socket_obj, None)

        # Connection with open will fail
        with self.assertRaises(osmocom.vty.exceptions.VTYChainedException):
            self.vty.open()
        # Remains disconnected
        self.assertEqual(self.vty._socket_obj, None)

class DroppedConnectionTestCase(MockSocketTestCase):
    """We defined a VTY connection to be in the closed state when self._socket_obj
    is set to None. Therefore, in the case of a socket that has failed, we
    need to ensure that it gets reset to None.
    """
    @classmethod
    def setUpClass(cls):
        cls.vty = osmocom.vty.base.BaseVTY('OpenBSC')

        cls.original_socket_obj = osmocom.vty.base.socket
        cls.mock_socket_obj = mock.MagicMock()
        osmocom.vty.base.socket.socket = mock.Mock()
        osmocom.vty.base.socket.socket.return_value = cls.mock_socket_obj

        # We also need to mock the check the recv loop uses to see if there more to read
        cls.original_select = osmocom.vty.base.select
        osmocom.vty.base.select = mock.Mock()

    @classmethod
    def tearDownClass(cls):
        osmocom.vty.base.select = cls.original_select
        osmocom.vty.base.socket = cls.original_socket_obj

    def setUp(self):
        osmocom.vty.base.select.select = self.select_fixture
        self.mock_socket_obj.sendall = self.sendall_fixture
        self.mock_socket_obj.recv = self.recv_fixture

    def select_fixture(self, rlist, wlist, xlist, timeout=None):
        if self.NUM_READS:
            return (rlist, [], [])
        else:
            return ([], [], [])

    def recv_fixture(self, _):
        if self.NUM_READS > 0:
            self.NUM_READS -= 1
            return b'EOM\r\nOpenBSC'
        return b''

    def sendall_fixture(self, _):
        if self.NUM_WRITES > 0:
            self.NUM_WRITES -= 1
        else:
            raise self.original_socket_obj.error()

    def test_failed_recv(self):
        """Tests that if a connection fails during read, we perform
        a disconnect."""

        # sendrecv does a read and write per request, so the 6th request
        # will fail on read
        self.NUM_READS = 5
        self.NUM_WRITES = 6

        self.assertEqual(self.vty._socket_obj, None)
        with self.vty as v:
            self.assertTrue(self.vty._socket_obj is not None)
            for i in range(self.NUM_READS):
                v.sendrecv('')
            # Call will fail on read
            with self.assertRaises(osmocom.vty.exceptions.VTYException):
                v.sendrecv('')
            self.assertEqual(self.vty._socket_obj, None)
        self.assertEqual(self.vty._socket_obj, None)

    def test_failed_send(self):
        """Tests that if a connection fails during write, we perform
        a disconnect."""

        # sendrecv does a read and write per request, so the 6th request
        # will fail on write
        self.NUM_READS = 6
        self.NUM_WRITES = 5

        self.assertEqual(self.vty._socket_obj, None)
        with self.vty as v:
            self.assertTrue(self.vty._socket_obj is not None)
            for i in range(self.NUM_WRITES):
                v.sendrecv('')
            # Call will fail on write
            with self.assertRaises(osmocom.vty.exceptions.VTYException):
                v.sendrecv('')
            self.assertEqual(self.vty._socket_obj, None)
        self.assertEqual(self.vty._socket_obj, None)
