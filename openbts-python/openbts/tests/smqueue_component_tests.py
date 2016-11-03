"""openbts.tests.smqueue_component_tests
tests for the SMQueue component

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import unittest

import mock

from openbts.components import SMQueue
from openbts.exceptions import InvalidRequestError
from openbts.codes import (SuccessCode, ErrorCode)


class SMQueueNominalConfigTestCase(unittest.TestCase):
  """Testing the components.SMQueue class.

  Applying nominal uses of the 'config' command and 'smqueue' target.
  """

  def setUp(self):
    self.smqueue_connection = SMQueue()
    # mock a zmq socket with a simple recv return value
    self.smqueue_connection.socket = mock.Mock()
    self.smqueue_connection.socket.recv.return_value = json.dumps({
      'code': 204,
      'data': 'sample',
      'dirty': 0
    })

  def test_create_config_raises_error(self):
    """Creating a config key should is not yet supported via NodeManager."""
    with self.assertRaises(InvalidRequestError):
      self.smqueue_connection.create_config('sample-key', 'sample-value')

  def test_read_config(self):
    """Reading a key should send a message over zmq and get a response."""
    response = self.smqueue_connection.read_config('sample-key')
    # check that we touched the socket to send the message
    self.assertTrue(self.smqueue_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'config',
      'action': 'read',
      'key': 'sample-key',
      'value': ''
    })
    # check that we've sent the expected message
    self.assertEqual(self.smqueue_connection.socket.send.call_args[0],
                     (expected_message,))
    # we should have touched the socket again to receive the reply
    self.assertTrue(self.smqueue_connection.socket.recv.called)
    # verify we received a valid response
    self.assertEqual(response.code, SuccessCode.NoContent)

  def test_update_config(self):
    """Updating a key should send a message over zmq and get a response."""
    response = self.smqueue_connection.update_config('sample-key',
                                                     'sample-value')
    self.assertTrue(self.smqueue_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'config',
      'action': 'update',
      'key': 'sample-key',
      'value': 'sample-value'
    })
    self.assertEqual(self.smqueue_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.smqueue_connection.socket.recv.called)
    self.assertEqual(response.code, SuccessCode.NoContent)

  def test_delete_config_raises_error(self):
    """Deleting a config key should is not yet supported via NodeManager."""
    with self.assertRaises(InvalidRequestError):
      self.smqueue_connection.delete_config('sample-key')


class SMQueueOffNominalConfigTestCase(unittest.TestCase):
  """Testing the components.SMQueue class.

  Examining off-nominal behaviors of the 'config' command and 'smqueue' target.
  """

  def setUp(self):
    self.smqueue_connection = SMQueue()
    # mock a zmq socket
    self.smqueue_connection.socket = mock.Mock()

  def test_read_config_unknown_key(self):
    """Reading a nonexistent key raises an error."""
    self.smqueue_connection.socket.recv.return_value = json.dumps({
      'code': 404,
    })
    with self.assertRaises(InvalidRequestError):
      self.smqueue_connection.read_config('nonexistent-key')

  def test_update_config_invalid_value(self):
    """Updating a value outside the allowed range raises an error."""
    self.smqueue_connection.socket.recv.return_value = json.dumps({
      'code': 406,
    })
    with self.assertRaises(InvalidRequestError):
      self.smqueue_connection.update_config('sample-key', 'sample-value')

  def test_update_config_storing_value_fails(self):
    """If storing the new value fails, an error should be raised."""
    self.smqueue_connection.socket.recv.return_value = json.dumps({
      'code': 500,
    })
    with self.assertRaises(InvalidRequestError):
      self.smqueue_connection.update_config('sample-key', 'sample-value')


class SMQueueNominalGetVersionTestCase(unittest.TestCase):
  """Testing the 'get_version' command on the components.smqueue class."""

  def setUp(self):
    self.smqueue_connection = SMQueue()
    # mock a zmq socket with a simple recv return value
    self.smqueue_connection.socket = mock.Mock()
    self.smqueue_connection.socket.recv.return_value = json.dumps({
      'code': 200,
      'data': 'release 4'
    })

  def test_get_version(self):
    """The 'get_version' command should return a response."""
    response = self.smqueue_connection.get_version()
    self.assertTrue(self.smqueue_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'version',
      'action': '',
      'key': '',
      'value': ''
    })
    self.assertEqual(self.smqueue_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.smqueue_connection.socket.recv.called)
    self.assertEqual(response.data, 'release 4')
