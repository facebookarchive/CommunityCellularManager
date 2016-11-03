"""openbts.tests.base_component_tests
tests for the base component class

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
from multiprocessing import Process
import time
import unittest

import zmq

from openbts.core import BaseComponent
from openbts.exceptions import TimeoutError
from openbts.codes import (SuccessCode, ErrorCode)


class BaseComponentTestCase(unittest.TestCase):
  """Testing the core.BaseComponent class.

  Contains a simple zmq server with a fixed latency.  The simulated latency
  allows us to test socket timeout features.  The idea is to run the demo
  server in another process and then connect through a test client.
  """

  # The demo server will wait this many seconds before replying.
  RESPONSE_DELAY = 0.1
  DEMO_ADDRESS = 'tcp://127.0.0.1:7890'

  def zmq_demo_server(self):
    """Run a small zmq testing server."""
    context = zmq.Context()
    server_socket = context.socket(zmq.REP)
    server_socket.bind(self.DEMO_ADDRESS)
    server_socket.recv()
    response = json.dumps({'code': 200, 'data': 'testing', 'dirty': 0})
    # Delay a bit before sending the reply.
    time.sleep(self.RESPONSE_DELAY)
    server_socket.send(response)

  def setUp(self):
    """Setup the zmq test server."""
    self.demo_server_process = Process(target=self.zmq_demo_server)
    self.demo_server_process.start()

  def tearDown(self):
    """Shutdown the demo zmq server."""
    self.demo_server_process.terminate()
    self.demo_server_process.join()

  def test_socket_timeout(self):
    """Base socket should raise a TimeoutError after receiving no reply."""
    # The server will delay before sending response so we set the timeout to be
    # a bit less than that amount.
    component = BaseComponent(socket_timeout=self.RESPONSE_DELAY*0.9)
    component.address = self.DEMO_ADDRESS
    component.socket.connect(self.DEMO_ADDRESS)
    with self.assertRaises(TimeoutError):
      component.read_config('sample-key')
