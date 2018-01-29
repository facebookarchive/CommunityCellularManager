"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Integration testing -- requires OpenBTS components to be running.

Usage (from the repo's root):
  $ nosetests
  $ nosetests openbts.tests.integration_tests:SIPAuthServeTest
  $ nosetests openbts.tests.integration_tests:SIPAuthServeTest.test_one_thing

Warning: this will change live values in OpenBTS.
"""

import unittest

import openbts


class VersionTest(unittest.TestCase):
  """We can read version data without throwing errors."""

  def test_query_openbts_version(self):
    connection = openbts.components.OpenBTS()
    response = connection.get_version()
    self.assertTrue(isinstance(response.data, unicode))  # noqa: F821 T25377293 Grandfathered in

  def test_query_sipauthserve_version(self):
    connection = openbts.components.SIPAuthServe()
    response = connection.get_version()
    self.assertTrue(isinstance(response.data, unicode))  # noqa: F821 T25377293 Grandfathered in

  def test_query_smqueue_version(self):
    connection = openbts.components.SMQueue()
    response = connection.get_version()
    self.assertTrue(isinstance(response.data, unicode))  # noqa: F821 T25377293 Grandfathered in


class ConfigReadTest(unittest.TestCase):
  """We can read config vars without throwing errors."""

  def test_read_openbts_config(self):
    connection = openbts.components.OpenBTS()
    response = connection.read_config('Control.NumSQLTries')
    self.assertTrue(isinstance(response.data, dict))

  def test_read_sipauthserve_config(self):
    connection = openbts.components.SIPAuthServe()
    response = connection.read_config('Log.Alarms.Max')
    self.assertTrue(isinstance(response.data, dict))

  def test_read_smqueue_config(self):
    connection = openbts.components.SMQueue()
    response = connection.read_config('Bounce.Code')
    self.assertTrue(isinstance(response.data, dict))


class ConfigUpdateTest(unittest.TestCase):
  """We can update config vars without throwing errors."""

  def test_update_openbts_config(self):
    connection = openbts.components.OpenBTS()
    key = 'Control.NumSQLTries'
    response = connection.read_config(key)
    original_value = response.data['value']
    connection.update_config(key, 6)
    connection.update_config(key, original_value)

  def test_update_sipauthserve_config(self):
    connection = openbts.components.SIPAuthServe()
    key = 'Log.Alarms.Max'
    response = connection.read_config(key)
    original_value = response.data['value']
    connection.update_config(key, 12)
    connection.update_config(key, original_value)

  def test_update_smqueue_config(self):
    connection = openbts.components.SMQueue()
    key = 'Bounce.Code'
    response = connection.read_config(key)
    original_value = response.data['value']
    connection.update_config(key, 555)
    connection.update_config(key, original_value)


class OpenBTSMonitoringTest(unittest.TestCase):

  def test_monitor_openbts(self):
    connection = openbts.components.OpenBTS()
    response = connection.monitor()
    self.assertIn('noiseRSSI', response.data)


class OpenBTSTMSITableTest(unittest.TestCase):
  """Tests the TMSI table functionality"""

  def test_tmsi_table(self):
    """This test is pretty primitive since we can't add TMSI entries
    from python yet."""
    connection = openbts.components.OpenBTS()
    response = connection.tmsis()
    self.assertEqual(list, type(response))


class OpenBTSLoadTest(unittest.TestCase):
  """Tests the get_load functionality"""

  def test_get_load(self):
    connection = openbts.components.OpenBTS()
    response = connection.get_load()
    self.assertEqual(dict, type(response))


class SIPAuthServeTest(unittest.TestCase):
  """Testing SIPAuthServe subscriber and number operations."""

  def setUp(self):
    self.conn = openbts.components.SIPAuthServe(socket_timeout=0.1)
    self.sub_a_imsi = 'IMSI000123'
    self.sub_b_imsi = 'IMSI000789'
    self.tearDown()
    self.conn.create_subscriber(self.sub_a_imsi, '5551234', '127.0.0.1',
                                '8888')
    self.conn.create_subscriber(self.sub_b_imsi, '5556789', '123.234.123.234',
                                '8000', ki=6789)

  def tearDown(self):
    self.conn.delete_subscriber(imsi=self.sub_a_imsi)
    self.conn.delete_subscriber(imsi=self.sub_b_imsi)

  def test_subscriber_count(self):
    self.assertEqual(2, self.conn.count_subscribers())

  def test_get_all_subscribers(self):
    result = self.conn.get_subscribers()
    expected_data = [{
      'name': self.sub_a_imsi,
      'openbts_ipaddr': '127.0.0.1',
      'openbts_port': '8888',
      'numbers': ['5551234'],
      'account_balance': '0',
      'caller_id': '5551234',
    }, {
      'name': self.sub_b_imsi,
      'openbts_ipaddr': '123.234.123.234',
      'openbts_port': '8000',
      'numbers': ['5556789'],
      'account_balance': '0',
      'caller_id': '5556789',
    }]
    self.assertItemsEqual(expected_data, result)

  def test_subscriber_filter(self):
    result = self.conn.get_subscribers(imsi=self.sub_a_imsi)
    expected_data = [{
      'name': self.sub_a_imsi,
      'openbts_ipaddr': u'127.0.0.1',
      'openbts_port': u'8888',
      'numbers': [u'5551234'],
      'account_balance': u'0',
      'caller_id': u'5551234',
    }]
    self.assertEqual(expected_data, result)

  def test_subscriber_filter_nonexistent_imsi(self):
    result = self.conn.get_subscribers(imsi='IMSI00993322')
    expected_data = []
    self.assertEqual(expected_data, result)

  def test_create_duplicate_subscriber(self):
    """If the IMSI already exists, this should fail."""
    with self.assertRaises(ValueError):
      self.conn.create_subscriber(self.sub_a_imsi, '5554321', '127.123.2.3',
                                  '4499')

  def test_get_openbts_ipaddr(self):
    self.assertEqual('123.234.123.234',
                     self.conn.get_openbts_ipaddr(self.sub_b_imsi))

  def test_get_openbts_port(self):
    self.assertEqual('8000', self.conn.get_openbts_port(self.sub_b_imsi))

  def test_get_single_number(self):
    self.assertEqual(['5556789'], self.conn.get_numbers(self.sub_b_imsi))

  def test_set_openbts_ipaddr(self):
    self.conn.update_openbts_ipaddr(self.sub_a_imsi, '244.255.200.201')
    self.assertEqual('244.255.200.201',
                     self.conn.get_openbts_ipaddr(self.sub_a_imsi))

  def test_set_openbts_port(self):
    self.conn.update_openbts_port(self.sub_a_imsi, '9999')
    self.assertEqual('9999', self.conn.get_openbts_port(self.sub_a_imsi))

  def test_associate_more_numbers(self):
    """A subscriber can have multiple associated numbers."""
    self.conn.add_number(self.sub_a_imsi, '5557744')
    expected_numbers = ['5551234', '5557744']
    self.assertItemsEqual(expected_numbers,
                          self.conn.get_numbers(self.sub_a_imsi))

  def test_add_preexisting_number(self):
    """If we try to add a pre-existing number, do nothing."""
    self.conn.add_number(self.sub_a_imsi, '5551234')
    expected_numbers = ['5551234']
    self.assertItemsEqual(expected_numbers,
                          self.conn.get_numbers(self.sub_a_imsi))

  def test_delete_last_number(self):
    with self.assertRaises(ValueError):
      self.conn.delete_number(self.sub_a_imsi, '5551234')

  def test_delete_single_number(self):
    self.conn.add_number(self.sub_a_imsi, '5557744')
    self.conn.delete_number(self.sub_a_imsi, '5551234')
    expected_numbers = ['5557744']
    self.assertItemsEqual(expected_numbers,
                          self.conn.get_numbers(self.sub_a_imsi))

  def test_delete_subscribers(self):
    first_count = self.conn.count_subscribers()
    self.conn.delete_subscriber(imsi=self.sub_a_imsi)
    self.conn.delete_subscriber(imsi=self.sub_b_imsi)
    self.assertEqual(first_count - 2, self.conn.count_subscribers())

  def test_get_imsi_from_number(self):
    result = self.conn.get_imsi_from_number('5551234')
    self.assertEqual(self.sub_a_imsi, result)

  def test_get_imsi_from_nonexistent_number(self):
    with self.assertRaises(openbts.exceptions.InvalidRequestError):
      self.conn.get_imsi_from_number('5558876')

  def test_get_account_balance(self):
    result = self.conn.get_account_balance(self.sub_a_imsi)
    self.assertEqual('0', result)

  def test_get_account_balance_from_nonexistent_imsi(self):
    with self.assertRaises(openbts.exceptions.InvalidRequestError):
      self.conn.get_account_balance('IMSI000443322')

  def test_update_account_balance(self):
    self.conn.update_account_balance(self.sub_a_imsi, '1000')
    result = self.conn.get_account_balance(self.sub_a_imsi)
    self.assertEqual('1000', result)

  def test_update_account_balance_invalid_type(self):
    """Account balances must be integer values."""
    with self.assertRaises(TypeError):
      self.conn.update_account_balance(self.sub_a_imsi, 999)
    with self.assertRaises(TypeError):
      self.conn.update_account_balance(self.sub_a_imsi, 9.99)


class CallerIDTest(unittest.TestCase):
  """Testing SIPAuthServe caller ID operations."""

  def setUp(self):
    self.conn = openbts.components.SIPAuthServe(socket_timeout=0.1)
    self.sub_a_imsi = 'IMSI000123'
    self.sub_b_imsi = 'IMSI000789'
    self.tearDown()
    self.conn.create_subscriber(self.sub_a_imsi, '5551234', '127.0.0.1',
                                '8888')
    self.conn.create_subscriber(self.sub_b_imsi, '5556789', '123.234.123.234',
                                '8000', ki=6789)

  def tearDown(self):
    self.conn.delete_subscriber(imsi=self.sub_a_imsi)
    self.conn.delete_subscriber(imsi=self.sub_b_imsi)

  def test_get_caller_id(self):
    self.assertEqual('5556789', self.conn.get_caller_id(self.sub_b_imsi))

  def test_set_caller_id_before_adding_number(self):
    """The new caller ID must already be associated with the subscriber."""
    with self.assertRaises(ValueError):
      self.conn.update_caller_id(self.sub_a_imsi, '5553232')

  def test_set_caller_id_after_associating_number(self):
    new_number = '5557744'
    self.conn.add_number(self.sub_a_imsi, new_number)
    self.conn.update_caller_id(self.sub_a_imsi, new_number)
    self.assertEqual(new_number, self.conn.get_caller_id(self.sub_a_imsi))

  def test_delete_caller_id_number(self):
    """Another number will be promoted to the caller_id."""
    new_number = '5557744'
    self.conn.add_number(self.sub_a_imsi, new_number)
    # The original number (added in setUp) is the caller_id until it's deleted.
    self.assertEqual('5551234', self.conn.get_caller_id(self.sub_a_imsi))
    self.conn.delete_number(self.sub_a_imsi, '5551234')
    self.assertEqual(new_number, self.conn.get_caller_id(self.sub_a_imsi))


class GPRSTest(unittest.TestCase):
  """Testing GPRS usage (experimental).

  This is an "instantaneous" API so the online test will only run to its
  fullest extent if a phone is online and using GPRS at the time.
  """

  @classmethod
  def setUpClass(cls):
    cls.conn = openbts.components.SIPAuthServe(socket_timeout=0.1)

  def test_online(self):
    """Get some GPRS parameters when a phone is active.

    If no phones are active, this test will short-circuit itself (but should
    still pass).
    """
    response = self.conn.get_gprs_usage()
    if not response:
      # No phones are online, exit.
      return
    self.assertEqual(dict, type(response))
    ms_data = response[response.keys()[0]]
    self.assertEqual(dict, type(ms_data))
    self.assertEqual(int, type(ms_data['uploaded_bytes']))
    self.assertEqual(int, type(ms_data['downloaded_bytes']))
    self.assertEqual(str, type(ms_data['ipaddr']))
