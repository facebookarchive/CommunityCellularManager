"""openbts.components
manages components in the OpenBTS application suite

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import re
import time

import envoy

from openbts.core import BaseComponent
from openbts.exceptions import InvalidRequestError
from openbts.exceptions import MalformedResponseError


class OpenBTS(BaseComponent):
  """Manages communication to an OpenBTS instance.

  Args:
    address: tcp socket for the zmq connection
  """

  def __init__(self, **kwargs):
    super(OpenBTS, self).__init__(**kwargs)
    self.address = kwargs.pop('address', 'tcp://127.0.0.1:45060')
    self.socket.connect(self.address)

  def __repr__(self):
    return 'OpenBTS component'

  def monitor(self):
    """Monitor channel loads, queue sizes and noise levels.

    See 3.4.4 of the OpenBTS 4.0 Manual for more info.

    Returns:
      Response instance
    """
    message = {
      'command': 'monitor',
      'action': '',
      'key': '',
      'value': ''
    }
    return self._send_and_receive(message)

  def tmsis(self, access_period=0, auth=1):
    """Gets all active subscribers from the TMSI table.

    Args:
      access_period: fetches all entries with ACCESS < access_period
                         (default=0 filter off)
      auth: fetches all entries with AUTH = auth
              Unauthorized = 0
              Authorized by registrar (default) = 1
              Open registration, not in sub db = 2
              Failed open registration = 3

    Returns a list of objects defined by the list of fields.  See section 4.3
    of the OpenBTS 4.0 Manual for more fields.
    """
    qualifiers = {
      'AUTH': str(auth)
    }
    message = {
      'command': 'tmsis',
      'action': 'read',
      'match': qualifiers,
      'fields': [
        'IMSI', 'TMSI', 'IMEI', 'AUTH', 'CREATED', 'ACCESSED', 'TMSI_ASSIGNED'
      ],
    }
    try:
      result = self._send_and_receive(message)
      tmsis = result.data
    except InvalidRequestError:
      return []
    if access_period > 0:
      access_cutoff_time = time.time() - access_period
      tmsis = filter(
        lambda entry: entry['ACCESSED'] > access_cutoff_time, tmsis)
    return tmsis

  def get_load(self):
    """Get the current BTS load.

    Returns a dict of the form: {
      'sdcch_load': 0,
      'sdcch_available': 4,
      'tchf_load': 0,
      'tchf_available': 3,
      'pch_active': 0,
      'pch_total': 0,
      'agch_active': 0,
      'agch_pending': 0,
      'gprs_current_pdchs': 4,
      'gprs_utilization_percentage': 4,
    }

    Terminology:
      SDCCH: a channel for short transactions (e.g. call setup, SMS)
      TCH/F: a full rate traffic channel
      PCH: a paging channel for service notifications
      AGCH: a channel for transmitting BTS responses to channel requests
    """
    response = envoy.run('/OpenBTS/OpenBTSCLI -c "load"', timeout=self.cli_timeout)
    if response.status_code != 0:
      raise InvalidRequestError(
        'CLI returned with non-zero status: %d' % response.status_code)
    items = response.std_out.split()

    try:
        res = {
          'sdcch_load': int(items[5].split('/')[0]),
          'sdcch_available': int(items[5].split('/')[1]),
          'tchf_load': int(items[8].split('/')[0]),
          'tchf_available': int(items[8].split('/')[1]),
          'pch_active': int(items[13].strip(',')),
          'pch_total': int(items[14]),
          'agch_active': int(items[19].strip(',')),
          'agch_pending': int(items[20]),
          'gprs_current_pdchs': int(items[26]),
          # We convert to a float first so that this can handle numbers in
          # scientific notation.
          'gprs_utilization_percentage': int(float(items[28].strip('%'))),
        }
    except (IndexError, ValueError):
        raise MalformedResponseError(
            'CLI returned with malformed response: %s' % response.std_out)

    return res

  def get_noise(self):
    """Get the current BTS noise values from the CLI.

    Returns a dict of the form: {
      'noise_rssi_db': -73,
      'noise_ms_rssi_target_db': -50,
    }
    """
    response = envoy.run('/OpenBTS/OpenBTSCLI -c "noise"', timeout=self.cli_timeout)
    if response.status_code != 0:
      raise InvalidRequestError(
        'CLI returned with non-zero status: %d' % response.status_code)
    items = response.std_out.split()
    try:
        return {
          'noise_rssi_db': int(items[3]),
          'noise_ms_rssi_target_db': int(items[12]),
        }
    except (IndexError, ValueError):
        raise MalformedResponseError(
            'CLI returned with malformed response: %s' % response.std_out)


class SIPAuthServe(BaseComponent):
  """Manages communication to the SIPAuthServe service.

  Args:
    address: tcp socket for the zmq connection
  """

  def __init__(self, **kwargs):
    super(SIPAuthServe, self).__init__(**kwargs)
    self.address = kwargs.pop('address', 'tcp://127.0.0.1:45064')
    self.socket.connect(self.address)

  def __repr__(self):
    return 'SIPAuthServe component'

  def count_subscribers(self):
    """Counts the total number of subscribers.

    Returns:
      integer number of subscribers
    """
    try:
      result = self.get_subscribers()
      return len(result)
    except InvalidRequestError:
      # 404 -- no subscribers found.
      return 0

  def get_subscribers(self, imsi=None):
    """Gets subscribers, optionally filtering by IMSI.

    Args:
      imsi: the IMSI to search by

    Returns:
      an empty array if no subscribers match the query, or an array of
      subscriber dicts, themselves of the form: {
        'name': 'IMSI000123',
        'openbts_ipaddr': '127.0.0.1',
        'openbts_port': '8888',
        'numbers': ['5551234', '5556789'],
        'account_balance': '1000',
      }
    """
    qualifiers = {}
    if imsi:
      qualifiers['name'] = imsi
    message = {
      'command': 'sip_buddies',
      'action': 'read',
      'match': qualifiers,
    }
    try:
      response = self._send_and_receive(message)
      subscribers = response.data
    except InvalidRequestError:
      return []
    # We get back every field in the SR, most of which are not useful.  We will
    # simplify each subscriber dict to show just a few attributes.  And we'll
    # attach additional info on associated numbers, account balance and the
    # caller ID.
    simplified_subscribers = []
    for subscriber in subscribers:
      simplified_subscriber = {
        'name': subscriber['name'],
        'openbts_ipaddr': subscriber['ipaddr'],
        'openbts_port': subscriber['port'],
        'numbers': self.get_numbers(subscriber['name']),
        'account_balance': self.get_account_balance(subscriber['name']),
        'caller_id': self.get_caller_id(subscriber['name']),
      }
      simplified_subscribers.append(simplified_subscriber)
    return simplified_subscribers

  def get_openbts_ipaddr(self, imsi):
    """Get the OpenBTS IP address of a subscriber."""
    fields = ['ipaddr']
    qualifiers = {
      'name': imsi
    }
    message = {
      'command': 'sip_buddies',
      'action': 'read',
      'match': qualifiers,
      'fields': fields,
    }
    response = self._send_and_receive(message)
    return response.data[0]['ipaddr']

  def get_openbts_port(self, imsi):
    """Get the OpenBTS port of a subscriber."""
    fields = ['port']
    qualifiers = {
      'name': imsi
    }
    message = {
      'command': 'sip_buddies',
      'action': 'read',
      'match': qualifiers,
      'fields': fields,
    }
    response = self._send_and_receive(message)
    return response.data[0]['port']

  def get_caller_id(self, imsi):
    """Get the caller ID of a subscriber."""
    fields = ['callerid']
    qualifiers = {
      'name': imsi
    }
    message = {
      'command': 'sip_buddies',
      'action': 'read',
      'match': qualifiers,
      'fields': fields,
    }
    response = self._send_and_receive(message)
    return response.data[0]['callerid']

  def get_numbers(self, imsi=None):
    """Get just the numbers (exten) associated with an IMSI.

    If imsi is None, get all dialdata.
    """
    fields = ['exten']
    qualifiers = {}
    if imsi:
      qualifiers['dial'] = imsi
    message = {
      'command': 'dialdata_table',
      'action': 'read',
      'match': qualifiers,
      'fields': fields,
    }
    try:
      response = self._send_and_receive(message)
      return [d['exten'] for d in response.data]
    except InvalidRequestError:
      return []

  def add_number(self, imsi, number):
    """Associate a new number with an IMSI.

    If the number's already been added, do nothing.
    """
    if number in self.get_numbers(imsi):
      return False
    message = {
      'command': 'dialdata_table',
      'action': 'create',
      'fields': {
        'dial': str(imsi),
        'exten': str(number),
      }
    }
    return self._send_and_receive(message)

  def delete_number(self, imsi, number):
    """De-associate a number with an IMSI."""
    # First see if the number is attached to the subscriber.
    numbers = self.get_numbers(imsi)
    if number not in numbers:
      raise ValueError('number %s not attached to IMSI %s' % (number, imsi))
    # Check if this is the only associated number.
    if len(numbers) == 1:
      raise ValueError('cannot delete number %s as it is the only number'
                       ' associated with IMSI %s' % (number, imsi))
    # See if this number is the caller ID.  If it is, promote another number
    # to be caller ID.
    if number == self.get_caller_id(imsi):
      numbers.remove(number)
      new_caller_id = numbers[-1]
      self.update_caller_id(imsi, new_caller_id)
    # Finally, delete the number.
    message = {
      'command': 'dialdata_table',
      'action': 'delete',
      'match': {
        'dial': str(imsi),
        'exten': str(number),
      }
    }
    result = self._send_and_receive(message)
    return result

  def create_subscriber(self, imsi, msisdn, openbts_ipaddr, openbts_port,
                        ki=''):
    """Add a subscriber.

    Technically we don't need every subscriber to have a number, but we'll just
    enforce this by convention.  We will also set the convention that a
    subscriber's name === their imsi.  Some things in NM are keyed on 'name'
    however, so we have to use both when making queries and updates.

    In calling this method we let NodeManager automatically set the sip_buddies
    callerid field to equal the providied msisdn.

    If the 'ki' argument is given, OpenBTS will use full auth.  Otherwise the
    system will use cache auth.  The values of IMSI, MSISDN and ki will all
    be cast to strings before the message is sent.

    Args:
      imsi: IMSI of the subscriber
      msisdn: MSISDN of the subscriber (their phone number)
      openbts_ipaddr: IP of the subscriber's OpenBTS instance
      openbts_port: port of the subscriber's OpenBTS instance
      ki: authentication key of the subscriber

    Returns:
      Response instance

    Raises:
      ValueError if the IMSI is already registered
    """
    # First we search for this IMSI to see if it is already registered.
    result = self.get_subscribers(imsi=imsi)
    if result:
      raise ValueError('IMSI %s is already registered.' % imsi)
    message = {
      'command': 'subscribers',
      'action': 'create',
      'fields': {
        'imsi': str(imsi),
        'msisdn': str(msisdn),
        'ipaddr': str(openbts_ipaddr),
        'port': str(openbts_port),
        'name': str(imsi),
        'ki': str(ki)
      }
    }
    response = self._send_and_receive(message)
    self.add_number(imsi, msisdn)
    return response

  def delete_subscriber(self, imsi):
    """Delete a subscriber by IMSI.

    Args:
      imsi: the IMSI of the to-be-deleted subscriber

    Returns:
      Response instance
    """
    message = {
      'command': 'subscribers',
      'action': 'delete',
      'match': {
        'imsi': str(imsi)
      }
    }
    response = self._send_and_receive(message)
    return response

  def update_openbts_ipaddr(self, imsi, new_openbts_ipaddr):
    """Updates a subscriber's IP address."""
    message = {
      'command': 'sip_buddies',
      'action': 'update',
      'match': {
        'name': imsi
      },
      'fields': {
        'ipaddr': new_openbts_ipaddr
      }
    }
    return self._send_and_receive(message)

  def update_openbts_port(self, imsi, new_openbts_port):
    """Updates a subscriber's OpenBTS port."""
    message = {
      'command': 'sip_buddies',
      'action': 'update',
      'match': {
        'name': imsi
      },
      'fields': {
        'port': new_openbts_port,
      }
    }
    return self._send_and_receive(message)

  def update_caller_id(self, imsi, new_caller_id):
    """Updates a subscriber's caller_id."""
    if new_caller_id not in self.get_numbers(imsi):
      raise ValueError('new caller id %s is not yet associated with subscriber'
                       ' %s' % (new_caller_id, imsi))
    message = {
      'command': 'sip_buddies',
      'action': 'update',
      'match': {
        'name': imsi
      },
      'fields': {
        'callerid': new_caller_id,
      }
    }
    return self._send_and_receive(message)

  def get_imsi_from_number(self, number):
    """Translate a number into an IMSI.

    Args:
      number: a phone number

    Returns:
      the matching IMSI

    Raises:
      InvalidRequestError if the number does not exist
    """
    qualifiers = {
      'exten': number
    }
    fields = ['dial', 'exten']
    message = {
      'command': 'dialdata_table',
      'action': 'read',
      'match': qualifiers,
      'fields': fields,
    }
    result = self._send_and_receive(message)
    return result.data[0]['dial']

  def get_account_balance(self, imsi):
    """Get the account balance of a subscriber."""
    fields = ['account_balance']
    qualifiers = {
      'name': imsi
    }
    message = {
      'command': 'sip_buddies',
      'action': 'read',
      'match': qualifiers,
      'fields': fields,
    }
    response = self._send_and_receive(message)
    return response.data[0]['account_balance']

  def update_account_balance(self, imsi, new_account_balance):
    """Updates a subscriber's account_balance.

    Args:
      imsi: the subscriber-of-interest
      new_account_balance: value of the new balance (str)

    Raises:
      TypeError if the new balance is not a string
    """
    if not isinstance(new_account_balance, str):
      raise TypeError
    message = {
      'command': 'sip_buddies',
      'action': 'update',
      'match': {
        'name': imsi
      },
      'fields': {
        'account_balance': new_account_balance
      }
    }
    return self._send_and_receive(message)

  def get_gprs_usage(self, target_imsi=None):
    """Get all available GPRS data, or that of a specific IMSI (experimental).

    Will return a dict of the form: {
      'ipaddr': '192.168.99.1',
      'downloaded_bytes': 200,
      'uploaded_bytes': 100,
    }

    Or, if no IMSI is specified, multiple dicts like the one above will be
    returned as part of a larger dict, keyed by IMSI.

    Args:
      target_imsi: the subsciber-of-interest
    """
    response = envoy.run('/OpenBTS/OpenBTSCLI -c "gprs list"', timeout=self.cli_timeout)
    if response.status_code != 0:
      raise InvalidRequestError(
        'CLI returned with non-zero status: %d' % response.status_code)
    result = {}
    for ms_block in response.std_out.split('MS#'):
      try:
        # Get the IMSI.
        match = re.search(r'imsi=[\d]{15}', ms_block)
        imsi = 'IMSI%s' % match.group(0).split('=')[1]
        # Get the IP.
        match = re.search(r'IPs=\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', ms_block)
        ipaddr = match.group(0).split('=')[1]
        # Get the uploaded and downloaded bytes.
        match = re.search(r'Bytes:[0-9]+up\/[0-9]+down', ms_block)
        count = match.group(0).split(':')[1]
        uploaded_bytes = int(count.split('/')[0].strip('up'))
        downloaded_bytes = int(count.split('/')[1].strip('down'))
      except AttributeError:
        # No match found.
        continue
      except ValueError:
        # Casting to int failed.
        continue
      # See if we already have an entry for the same IMSI -- we sometimes see
      # duplicates.  If we do have an entry already, sum the byte counts across
      # entries.
      if imsi in result:
        uploaded_bytes += result[imsi]['uploaded_bytes']
        downloaded_bytes += result[imsi]['downloaded_bytes']
      result[imsi] = {
        'ipaddr': ipaddr,
        'uploaded_bytes': uploaded_bytes,
        'downloaded_bytes': downloaded_bytes,
      }
    # If, after all that parsing, we still haven't found any matches, return
    # None instead of the empty dict.
    if result == {}:
      return None
    # If a specific IMSI was specified, return its data alone if it's in the
    # result.  If it's not in the parsed result, return None.
    if target_imsi and target_imsi not in result.keys():
      return None
    elif target_imsi:
      return result[target_imsi]
    # If no IMSI was specified, return all of the parsed data.
    return result


class SMQueue(BaseComponent):
  """Manages communication to the SMQueue service.

  Args:
    address: tcp socket for the zmq connection
  """

  def __init__(self, **kwargs):
    super(SMQueue, self).__init__(**kwargs)
    self.address = kwargs.pop('address', 'tcp://127.0.0.1:45063')
    self.socket.connect(self.address)

  def __repr__(self):
    return 'SMQueue component'
