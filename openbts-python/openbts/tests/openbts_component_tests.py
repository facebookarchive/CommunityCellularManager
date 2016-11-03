"""openbts.tests.openbts_component_tests
tests for the OpenBTS component

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import time
import unittest
import mock

import openbts
from openbts.components import OpenBTS
from openbts.exceptions import InvalidRequestError
from openbts.codes import SuccessCode
from openbts.tests import get_fixture_path
from openbts.tests import mocks

class OpenBTSNominalConfigTestCase(unittest.TestCase):
  """Testing the components.OpenBTS class.

  Applying nominal uses of the 'config' command and 'openbts' target.
  """

  def setUp(self):
    self.openbts_connection = OpenBTS()
    # mock a zmq socket with a simple recv return value
    self.openbts_connection.socket = mock.Mock()
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 204,
      'data': 'sample',
      'dirty': 0
    })

  def test_create_config_raises_error(self):
    """Creating a config key should is not yet supported via NodeManager."""
    with self.assertRaises(InvalidRequestError):
      self.openbts_connection.create_config('sample-key', 'sample-value')

  def test_read_config(self):
    """Reading a key should send a message over zmq and get a response."""
    response = self.openbts_connection.read_config('sample-key')
    # check that we touched the socket to send the message
    self.assertTrue(self.openbts_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'config',
      'action': 'read',
      'key': 'sample-key',
      'value': ''
    })
    # check that we've sent the expected message
    self.assertEqual(self.openbts_connection.socket.send.call_args[0],
                     (expected_message,))
    # we should have touched the socket again to receive the reply
    self.assertTrue(self.openbts_connection.socket.recv.called)
    # verify we received a valid response
    self.assertEqual(response.code, SuccessCode.NoContent)

  def test_update_config(self):
    """Updating a key should send a message over zmq and get a response."""
    response = self.openbts_connection.update_config('sample-key',
                                                     'sample-value')
    self.assertTrue(self.openbts_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'config',
      'action': 'update',
      'key': 'sample-key',
      'value': 'sample-value'
    })
    self.assertEqual(self.openbts_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.openbts_connection.socket.recv.called)
    self.assertEqual(response.code, 204)

  def test_delete_config_raises_error(self):
    """Deleting a config key should is not yet supported via NodeManager."""
    with self.assertRaises(InvalidRequestError):
      self.openbts_connection.delete_config('sample-key')

  def test_responses_with_no_dirty_param(self):
    """We should handle responses that don't have the 'dirty' attribute."""
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 200,
      'data': 'sample'
    })
    response = self.openbts_connection.read_config('sample-key')
    self.assertEqual(response.code, SuccessCode.OK)

  def test_responses_with_no_data_param(self):
    """We should handle responses that don't have the 'data' attribute."""
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 200,
    })
    response = self.openbts_connection.read_config('sample-key')
    self.assertEqual(response.code, SuccessCode.OK)


class OpenBTSOffNominalConfigTestCase(unittest.TestCase):
  """Testing the components.OpenBTS class.

  Examining off-nominal behaviors of the 'config' command and 'openbts' target.
  """

  def setUp(self):
    self.openbts_connection = OpenBTS()
    # mock a zmq socket
    self.openbts_connection.socket = mock.Mock()

  def test_read_config_unknown_key(self):
    """Reading a nonexistent key raises an error."""
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 404,
    })
    with self.assertRaises(InvalidRequestError):
      self.openbts_connection.read_config('nonexistent-key')

  def test_update_config_invalid_value(self):
    """Updating a value outside the allowed range raises an error."""
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 406,
    })
    with self.assertRaises(InvalidRequestError):
      self.openbts_connection.update_config('sample-key', 'sample-value')

  def test_update_config_storing_value_fails(self):
    """If storing the new value fails, an error should be raised."""
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 500,
    })
    with self.assertRaises(InvalidRequestError):
      self.openbts_connection.update_config('sample-key', 'sample-value')


class OpenBTSNominalGetVersionTestCase(unittest.TestCase):
  """Testing the 'get_version' command on the components.OpenBTS class."""

  def setUp(self):
    self.openbts_connection = OpenBTS()
    # mock a zmq socket with a simple recv return value
    self.openbts_connection.socket = mock.Mock()
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 200,
      'data': 'release 4.0.0.8025'
    })

  def test_get_version(self):
    """The 'get_version' command should return a response."""
    response = self.openbts_connection.get_version()
    self.assertTrue(self.openbts_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'version',
      'action': '',
      'key': '',
      'value': ''
    })
    self.assertEqual(self.openbts_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.openbts_connection.socket.recv.called)
    self.assertEqual(response.data, 'release 4.0.0.8025')


class OpenBTSNominalTMSIsTestCase(unittest.TestCase):
  """Testing the 'tmsis' command on the components.OpenBTS class."""

  def setUp(self):
    self.openbts_connection = OpenBTS()
    # mock a zmq socket with a simple recv return value
    self.openbts_connection.socket = mock.Mock()
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 200,
      'data': [
        {
          'IMSI': '901550000000084',
          'TMSI': '0x40000000',
          'IMEI': '355534065410400',
          'AUTH': '2',
          'CREATED': time.time() - 300,
          'ACCESSED': time.time() - 30,
          'TMSI_ASSIGNED': '0'
        },
        {
          'IMSI': '901550000000082',
          'TMSI': '0x40000000',
          'IMEI': '355534065410401',
          'AUTH': '2',
          'CREATED': time.time() - 900,
          'ACCESSED': time.time() - 180,
          'TMSI_ASSIGNED': '0'
        }
      ]
    })

  def test_tmsis(self):
    """The 'tmsis' command should return a response."""
    response = self.openbts_connection.tmsis(access_period=90)
    self.assertTrue(self.openbts_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'tmsis',
      'action': 'read',
      'match': {'AUTH': '1'},
      'fields': [ 'IMSI', 'TMSI', 'IMEI', 'AUTH', 'CREATED', 'ACCESSED',
                  'TMSI_ASSIGNED']
    })
    self.assertEqual(self.openbts_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.openbts_connection.socket.recv.called)
    self.assertEqual(len(response), 1)
    self.assertEqual(response[0]['IMSI'], '901550000000084')


class OpenBTSNominalMonitorTestCase(unittest.TestCase):
  """Testing the 'monitor' command on the components.OpenBTS class."""

  def setUp(self):
    self.openbts_connection = OpenBTS()
    # mock a zmq socket with a simple recv return value
    self.openbts_connection.socket = mock.Mock()
    self.openbts_connection.socket.recv.return_value = json.dumps({
      'code': 200,
      'data': {
        'noiseRSSI': -68
      }
    })

  def test_monitor(self):
    """The 'monitor' command should return a response."""
    response = self.openbts_connection.monitor()
    self.assertTrue(self.openbts_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'monitor',
      'action': '',
      'key': '',
      'value': ''
    })
    self.assertEqual(self.openbts_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.openbts_connection.socket.recv.called)
    self.assertEqual(response.data['noiseRSSI'], -68)


class LoadTest(unittest.TestCase):
  """Getting load data by invoking the OpenBTSCLI."""

  @classmethod
  def setUpClass(cls):
    """We use envoy to call the OpenBTSCLI so we'll monkeypatch that module."""
    cls.original_envoy = openbts.components.envoy
    cls.mock_envoy = mocks.MockEnvoy(return_text=None)
    openbts.components.envoy = cls.mock_envoy
    cls.openbts = OpenBTS()
    # Setup a path to the CLI output.
    cls.cli_output_path = get_fixture_path('load.txt')

  @classmethod
  def tearDownClass(cls):
    """Repair the envoy monkeypatch."""
    openbts.components.envoy = cls.original_envoy

  def test_one(self):
    """We can get load data."""
    with open(self.cli_output_path) as output:
      self.mock_envoy.return_text = output.read()
    expected = {
      'sdcch_load': 2,
      'sdcch_available': 4,
      'tchf_load': 1,
      'tchf_available': 3,
      'pch_active': 3,
      'pch_total': 7,
      'agch_active': 5,
      'agch_pending': 9,
      'gprs_current_pdchs': 4,
      'gprs_utilization_percentage': 41,
    }
    self.assertEqual(expected, self.openbts.get_load())

  def test_low_gprs_utilization(self):
    """We can handle gprs utilization in scientific notation."""
    cli_output_path = get_fixture_path('load_low_gprs.txt')
    with open(cli_output_path) as output:
      self.mock_envoy.return_text = output.read()
    expected = {
      'sdcch_load': 2,
      'sdcch_available': 4,
      'tchf_load': 1,
      'tchf_available': 3,
      'pch_active': 3,
      'pch_total': 7,
      'agch_active': 5,
      'agch_pending': 9,
      'gprs_current_pdchs': 4,
      'gprs_utilization_percentage': 0,
    }
    self.assertEqual(expected, self.openbts.get_load())


class NoiseTest(unittest.TestCase):
  """Getting noise data by invoking the OpenBTSCLI."""

  @classmethod
  def setUpClass(cls):
    """We use envoy to call the OpenBTSCLI so we'll monkeypatch that module."""
    cls.original_envoy = openbts.components.envoy
    cls.mock_envoy = mocks.MockEnvoy(return_text=None)
    openbts.components.envoy = cls.mock_envoy
    cls.openbts = OpenBTS()
    # Setup a path to the CLI output.
    cls.cli_output_path = get_fixture_path('noise.txt')

  @classmethod
  def tearDownClass(cls):
    """Repair the envoy monkeypatch."""
    openbts.components.envoy = cls.original_envoy

  def test_one(self):
    """We can get noise data."""
    with open(self.cli_output_path) as output:
      self.mock_envoy.return_text = output.read()
    expected = {
      'noise_rssi_db': -72,
      'noise_ms_rssi_target_db': -55,
    }
    self.assertEqual(expected, self.openbts.get_noise())
