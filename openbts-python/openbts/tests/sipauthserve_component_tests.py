"""Tests for the SIPAuthServe component.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import unittest

import mock

import openbts
from openbts.components import SIPAuthServe
from openbts.exceptions import InvalidRequestError
from openbts.codes import SuccessCode
from openbts.tests import get_fixture_path
from openbts.tests import mocks

class SIPAuthServeNominalConfigTestCase(unittest.TestCase):
  """Testing the components.SIPAuthServe class.

  Applying nominal uses of the 'config' command and 'sipauthserve' target.
  """

  def setUp(self):
    self.sipauthserve_connection = SIPAuthServe()
    # mock a zmq socket with a simple recv return value
    self.sipauthserve_connection.socket = mock.Mock()
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 204,
      'data': 'sample',
      'dirty': 0
    })

  def test_create_config_raises_error(self):
    """Creating a config key should is not yet supported via NodeManager."""
    with self.assertRaises(InvalidRequestError):
      self.sipauthserve_connection.create_config('sample-key', 'sample-value')

  def test_read_config(self):
    """Reading a key should send a message over zmq and get a response."""
    response = self.sipauthserve_connection.read_config('sample-key')
    # check that we touched the socket to send the message
    self.assertTrue(self.sipauthserve_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'config',
      'action': 'read',
      'key': 'sample-key',
      'value': ''
    })
    # check that we've sent the expected message
    self.assertEqual(self.sipauthserve_connection.socket.send.call_args[0],
                     (expected_message,))
    # we should have touched the socket again to receive the reply
    self.assertTrue(self.sipauthserve_connection.socket.recv.called)
    # verify we received a valid response
    self.assertEqual(response.code, SuccessCode.NoContent)

  def test_update_config(self):
    """Updating a key should send a message over zmq and get a response."""
    response = self.sipauthserve_connection.update_config(
      'sample-key', 'sample-value')
    self.assertTrue(self.sipauthserve_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'config',
      'action': 'update',
      'key': 'sample-key',
      'value': 'sample-value'
    })
    self.assertEqual(self.sipauthserve_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.sipauthserve_connection.socket.recv.called)
    self.assertEqual(response.code, SuccessCode.NoContent)

  def test_delete_config_raises_error(self):
    """Deleting a config key should is not yet supported via NodeManager."""
    with self.assertRaises(InvalidRequestError):
      self.sipauthserve_connection.delete_config('sample-key')


class SIPAuthServeOffNominalConfigTestCase(unittest.TestCase):
  """Testing the components.SIPAuthServe class.

  Examining off-nominal behaviors of the 'config' command and 'sipauthserve'
  target.
  """

  def setUp(self):
    self.sipauthserve_connection = SIPAuthServe()
    # mock a zmq socket
    self.sipauthserve_connection.socket = mock.Mock()

  def test_read_config_unknown_key(self):
    """Reading a nonexistent key raises an error."""
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 404,
    })
    with self.assertRaises(InvalidRequestError):
      self.sipauthserve_connection.read_config('nonexistent-key')

  def test_update_config_invalid_value(self):
    """Updating a value outside the allowed range raises an error."""
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 406,
    })
    with self.assertRaises(InvalidRequestError):
      self.sipauthserve_connection.update_config('sample-key', 'sample-value')

  def test_update_config_storing_value_fails(self):
    """If storing the new value fails, an error should be raised."""
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 500,
    })
    with self.assertRaises(InvalidRequestError):
      self.sipauthserve_connection.update_config('sample-key', 'sample-value')


class SIPAuthServeNominalGetVersionTestCase(unittest.TestCase):
  """Testing the 'get_version' command on the components.SIPAuthServe class."""

  def setUp(self):
    self.sipauthserve_connection = SIPAuthServe()
    # mock a zmq socket with a simple recv return value
    self.sipauthserve_connection.socket = mock.Mock()
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 200,
      'data': 'release 7'
    })

  def test_get_version(self):
    """The 'get_version' command should return a response."""
    response = self.sipauthserve_connection.get_version()
    self.assertTrue(self.sipauthserve_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'version',
      'action': '',
      'key': '',
      'value': ''
    })
    self.assertEqual(self.sipauthserve_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.sipauthserve_connection.socket.recv.called)
    self.assertEqual(response.data, 'release 7')


class SIPAuthServeNominalSubscriberTestCase(unittest.TestCase):
  """Testing the components.SIPAuthServe class.

  Applying nominal uses of the 'subscribers' command and 'sipauthserve' target.
  """

  def setUp(self):
    self.sipauthserve_connection = SIPAuthServe()
    # mock a zmq socket with a simple recv return value
    self.sipauthserve_connection.socket = mock.Mock()
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 204,
      'data': [{'exten': '5551234', 'name': 'sample'}],
      'dirty': 0
    })

  def test_get_all_subscribers(self):
    """Should send a message over zmq and get a response."""
    # Using 'side_effect' to mock multiple return values from the socket.  This
    # method makes quite a few requests.
    self.sipauthserve_connection.socket.recv.side_effect = [
      json.dumps({
        'code': 200,
        'data': [{
          'name': 'subscriber_a',
          'exten': '5551234',
          'ipaddr': '127.0.0.1',
          'port': '5555'
        }, {
          'name': 'subscriber_b',
          'exten': '5559876',
          'ipaddr': '127.0.0.1',
          'port': '5555'
        }]
      }),
      json.dumps({'code': 200, 'data': [{'exten': '5551234'}]}),
      json.dumps({'code': 200, 'data': [{'account_balance': '3000'}]}),
      json.dumps({'code': 200, 'data': [{'callerid': '5551234'}]}),
      # Return values for a second mocked subscriber.
      json.dumps({'code': 200, 'data': [{'exten': '5559876'}]}),
      json.dumps({'code': 200, 'data': [{'account_balance': '100000'}]}),
      json.dumps({'code': 200, 'data': [{'callerid': '5559876'}]}),
    ]
    response = self.sipauthserve_connection.get_subscribers()
    self.assertTrue(self.sipauthserve_connection.socket.send.called)
    self.assertTrue(self.sipauthserve_connection.socket.recv.called)
    self.assertEqual(2, len(response))
    self.assertEqual('subscriber_a', response[0]['name'])
    self.assertEqual('100000', response[1]['account_balance'])

  def test_get_a_subscriber(self):
    """Requesting a subscriber should send a zmq message and get a response."""
    self.sipauthserve_connection.socket.recv.side_effect = [
      json.dumps({
        'code': 200,
        'data': [{
          'name': 'subscriber_a',
          'exten': '5551234',
          'ipaddr': '127.0.0.1',
          'port': '5555'
        }]
      }),
      json.dumps({'code': 200, 'data': [{'exten': '5551234'}]}),
      json.dumps({'code': 200, 'data': [{'account_balance': '3000'}]}),
      json.dumps({'code': 200, 'data': [{'callerid': '5551234'}]}),
    ]
    response = self.sipauthserve_connection.get_subscribers(imsi='IMSI000000')
    self.assertTrue(self.sipauthserve_connection.socket.send.called)
    self.assertTrue(self.sipauthserve_connection.socket.recv.called)
    self.assertEqual(1, len(response))
    self.assertEqual('subscriber_a', response[0]['name'])
    self.assertEqual('3000', response[0]['account_balance'])

  def test_create_subscriber_with_ki(self):
    """Creating a subscriber should send a zmq message and get a response."""
    self.sipauthserve_connection.socket.recv.side_effect = [
      # First, get_subs should reply with 'not found' since this sub is new.
      json.dumps({'code': 404}),
      # The actual create sub message should succeed.
      json.dumps({'code': 200}),
      # The add_number request triggers a number lookup (should fail) and then
      # an actual "dialdata_table create" message which should succeed.
      json.dumps({'code': 404}),
      json.dumps({'code': 200}),
      # Then the OpenBTS ipaddr and port updates should succeed.
      json.dumps({'code': 200}),
      json.dumps({'code': 200}),
    ]
    self.sipauthserve_connection.create_subscriber(
      310150123456789, 123456789, '127.0.0.1', '1234', ki='abc')

  def test_create_subscriber_sans_ki(self):
    """Creating a subscriber without a specficied ki uses zmq."""
    self.sipauthserve_connection.socket.recv.side_effect = [
      # First, get_subs should reply with 'not found' since this sub is new.
      json.dumps({'code': 404}),
      # The actual create sub message should succeed.
      json.dumps({'code': 200}),
      # The add_number request triggers a number lookup (should fail) and then
      # an actual "dialdata_table create" message which should succeed.
      json.dumps({'code': 404}),
      json.dumps({'code': 200}),
      # Then the OpenBTS ipaddr and port updates should succeed.
      json.dumps({'code': 200}),
      json.dumps({'code': 200}),
    ]
    self.sipauthserve_connection.create_subscriber(
      310150123456789, 123456789, '127.0.0.1', '1234')

  def test_delete_subscriber_by_imsi(self):
    """Deleting a subscriber by IMSI should use zmq."""
    response = self.sipauthserve_connection.delete_subscriber(310150123456789)
    self.assertTrue(self.sipauthserve_connection.socket.send.called)
    expected_message = json.dumps({
      'command': 'subscribers',
      'action': 'delete',
      'match': {
        'imsi': '310150123456789'
      }
    })
    self.assertEqual(self.sipauthserve_connection.socket.send.call_args[0],
                     (expected_message,))
    self.assertTrue(self.sipauthserve_connection.socket.recv.called)
    self.assertEqual(response.code, SuccessCode.NoContent)


class SIPAuthServeOffNominalSubscriberTestCase(unittest.TestCase):
  """Testing the components.SIPAuthServe class.

  Applying off-nominal uses of the 'subscribers' command and 'sipauthserve'
  target.
  """

  def setUp(self):
    self.sipauthserve_connection = SIPAuthServe()
    # mock a zmq socket with a simple recv return value
    self.sipauthserve_connection.socket = mock.Mock()
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 200,
      'data': 'sample',
      'dirty': 0
    })

  def test_get_nonexistent_subscribers(self):
    """Requesting a nonexistent subscriber returns an empty array."""
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 404,
      'data': 'not found'
    })
    response = self.sipauthserve_connection.get_subscribers(
      imsi='non-existent')
    self.assertEqual([], response)

  def test_delete_subscriber_when_sqlite_unavailable(self):
    """Invalid request when sqlite is unavailble."""
    self.sipauthserve_connection.socket.recv.return_value = json.dumps({
      'code': 503,
      'data': {
        'sip_buddies': 'something bad',
        'dialdata_table': 'this could be ok'
      }
    })
    with self.assertRaises(InvalidRequestError):
      self.sipauthserve_connection.delete_subscriber(310150123456789)


class GPRSTest(unittest.TestCase):
  """Getting GPRS usage info for a subscriber by invoking OpenBTSCLI."""

  @classmethod
  def setUpClass(cls):
    """We use envoy to call the OpenBTSCLI so we'll monkeypatch that module."""
    cls.original_envoy = openbts.components.envoy
    cls.mock_envoy = mocks.MockEnvoy(return_text=None)
    openbts.components.envoy = cls.mock_envoy
    cls.sipauthserve = SIPAuthServe()
    # Setup a path to the CLI output.
    cls.cli_output_path = get_fixture_path('gprs_list.txt')

  @classmethod
  def tearDownClass(cls):
    """Repair the envoy monkeypatch."""
    openbts.components.envoy = cls.original_envoy

  def test_gprs_disabled(self):
    """Envoy gets an empty reply when GPRS is disabled.

    This also occurs if phones are off and do not have IPs assigned.
    """
    self.mock_envoy.return_text = '\n'
    response = self.sipauthserve.get_gprs_usage()
    self.assertEqual(None, response)
    response = self.sipauthserve.get_gprs_usage(target_imsi='IMSI000123')
    self.assertEqual(None, response)

  def test_all_imsis(self):
    """We can get all available GPRS connection data."""
    # The command 'gprs list' returns a big string when IPs are assigned.
    with open(self.cli_output_path) as output:
      self.mock_envoy.return_text = output.read()
    expected_usage = {
      'IMSI901550000000022': {
        'ipaddr': '192.168.99.4',
        'uploaded_bytes': 53495,
        'downloaded_bytes': 139441,
      },
      'IMSI901550000000505': {
        'ipaddr': '192.168.99.1',
        'uploaded_bytes': 21254,
        'downloaded_bytes': 41016,
      },
      'IMSI901550000000504': {
        'ipaddr': '192.168.99.2',
        'uploaded_bytes': 111,
        'downloaded_bytes': 77,
      },
      'IMSI901550000000015': {
        'ipaddr': '192.168.99.3',
        'uploaded_bytes': 111,
        'downloaded_bytes': 77,
      },
    }
    self.assertEqual(expected_usage, self.sipauthserve.get_gprs_usage())

  def test_specific_imsi(self):
    """We can get data for a specific IMSI."""
    with open(self.cli_output_path) as output:
      self.mock_envoy.return_text = output.read()
    target_imsi = 'IMSI901550000000022'
    expected_usage = {
      'ipaddr': '192.168.99.4',
      'uploaded_bytes': 53495,
      'downloaded_bytes': 139441,
    }
    self.assertEqual(expected_usage,
                     self.sipauthserve.get_gprs_usage(target_imsi=target_imsi))

  def test_unknown_imsi(self):
    """Unknown IMSIs will return None."""
    with open(self.cli_output_path) as output:
      self.mock_envoy.return_text = output.read()
    target_imsi = 'IMSI000123'
    expected_usage = None
    self.assertEqual(expected_usage,
                     self.sipauthserve.get_gprs_usage(target_imsi=target_imsi))

  def test_duplicate_imsis(self):
    """We correctly handle duplicate IMSIs in the output of gprs list."""
    path = get_fixture_path('gprs_list_duplicate_imsis.txt')
    with open(path) as output:
      self.mock_envoy.return_text = output.read()
    expected_usage = {
      'IMSI901550000000544': {
        'ipaddr': '192.168.99.1',
        'uploaded_bytes': 45986,
        'downloaded_bytes': 76210,
      },
      'IMSI901550000000186': {
        'ipaddr': '192.168.99.2',
        'uploaded_bytes': 90625,
        'downloaded_bytes': 146420,
      },
      'IMSI901550000000545': {
        'ipaddr': '192.168.99.3',
        'uploaded_bytes': 93076,
        'downloaded_bytes': 147420,
      },
      'IMSI901550000000542': {
        'ipaddr': '192.168.99.4',
        'uploaded_bytes': 72894,
        'downloaded_bytes': 139771,
      },
    }
    print self.sipauthserve.get_gprs_usage()  # noqa: E999 T25377293 Grandfathered in
    self.assertEqual(expected_usage, self.sipauthserve.get_gprs_usage())
