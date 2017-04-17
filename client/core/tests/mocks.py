"""Some mocks used in various tests.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import collections
import time

import requests
from core.bts.base import BaseBTS
from core.subscriber.base import BaseSubscriber


class MockRequests(object):
    """Mocking the third party requests lib."""

    def __init__(self, return_code):
        """All methods will return the specified return_code."""
        self.response = requests.Response()
        self.Session = lambda: MockRequests(return_code)
        self.response.status_code = return_code
        self.post_endpoint = None
        self.post_headers = None
        self.post_data = None
        self.post_timeout = None

    def get(self, endpoint, params=None):
        """Mocking requests.get."""
        return self.response

    def post(self, endpoint, headers=None, data=None, timeout=None, cookies=None):
        """Mocking requests.post and capturing the data that's sent."""
        self.post_endpoint = endpoint
        self.post_headers = headers
        self.post_data = data
        self.post_timeout = timeout
        return self.response

class MockSubscriber(BaseSubscriber):
    """Mocks out core.subscriber"""

    def __init__(self):
        self.gprs_return_value = None
        self.get_subscriber_return_value = [{
            'name': 'IMSI901550000000084',
            'ipaddr': '127.0.0.1',
            'port': '8888',
            'numbers': ['5551234', '5556789'],
            'account_balance': '1000',
        }, {
            'name': 'IMSI901550000000082',
            'ipaddr': '127.0.0.1',
            'port': '8888',
            'numbers': ['5551235', '5156789'],
            'account_balance': '1000',
        }]

    @classmethod
    def get_subscriber_states(cls, imsis=None):
        return {"IMSI123": {"balance": "foo"}}

    def delete_number(self, imsi, number):
        pass

    def get_account_balance(self, imsi):
        return 1000

    def subtract_credit(self, imsi, amount):
        pass

    def get_imsi_from_number(self, number):
        return 'IMSI000227'

    def get_imsi_from_username(self, username):
        return username

    def get_subscribers(self, imsi=None):
        return self.get_subscriber_return_value

    def get_gprs_usage(self):
        return self.gprs_return_value

class MockBTS(BaseBTS):
    SERVICES = []
    REGISTERED_AUTH_VALUES = [1,2]

    def set_factory_config(self):
        raise NotImplementedError()

    def get_camped_subscribers(self, access_period=0, auth=2):
        if auth == 2:
            return [{
                'IMSI': '901550000000084',
                'TMSI': '0x40000000',
                'IMEI': '355534065410400',
                'AUTH': '2',
                'CREATED': time.time() - 300,
                'ACCESSED': time.time() - 30,
                'TMSI_ASSIGNED': '0'
            }, {
                'IMSI': '901550000000082',
                'TMSI': '0x40000000',
                'IMEI': '355534065410401',
                'AUTH': '2',
                'CREATED': time.time() - 900,
                'ACCESSED': time.time() - 180,
                'TMSI_ASSIGNED': '0'
            }]
        elif auth == 1:
            return [{
                'IMSI': '901550000000083',
                'TMSI': '0x40000004',
                'IMEI': '355534065410407',
                'AUTH': '1',
                'CREATED': time.time() - 1800,
                'ACCESSED': time.time() - 10,
                'TMSI_ASSIGNED': '0'
            }]


    def get_load(self):
        return {
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

    def get_noise(self):
        return {
            'noise_rssi_db': -25,
            'noise_ms_rssi_target_db': -33,
        }

    def get_band(self):
        return "GSM900"

    def get_arfcn_c0(self):
        return "51"

    def get_timer(self, timer):
      timers = {'3212': '6'}
      return timers[timer]

class MockEvents(object):
    """Mocking the core.events module."""

    def usage(self):
        return []

    class CheckinHandler(object):
        """Mocking core.events.CheckinHandler."""
        section_ctx = {}
        def __init__(self, response_text):
            self.response_text = response_text

    class EventStore(object):
        def __init__(self):
            self.mock_events = []

        def modified_subs(self):
            imsis = set()
            for e in self.mock_events:
                imsis.add(e['imsi'])
            return list(imsis)

        def add(self, event_dict):
            self.mock_events.append(event_dict)


class MockSnowflake(object):
    """Mocking snowflake."""

    def __init__(self, uuid='09031a16-6361-4a93-a934-24c990ef4b87'):
        self.uuid = uuid

    def snowflake(self):
        return self.uuid


class MockDelegator(object):
    """Mocking the delegatyor package."""

    def __init__(self, return_text):
        self.return_text = return_text

    class Response(object):
        """Mock delegator response."""

        def __init__(self, return_text):
            self.out = return_text
            self.return_code = 0

    def run(self, _):
        return self.Response(self.return_text)


class MockPSUtil(object):
    """Mocking the psutil package.

    Many of these methods returned namedtuples.
    """

    def __init__(self, utilization):
        """Init this mock package with a dict of utilization values.

        These values will be returned by the mocked methods below.
        """
        self.utilization = utilization

    def cpu_percent(self, interval=None):
        return self.utilization['cpu_percent']

    def virtual_memory(self):
        mem = collections.namedtuple('Memory', 'percent')
        return mem(percent=self.utilization['memory_percent'])

    def disk_usage(self, path):
        disk = collections.namedtuple('Disk', 'percent')
        return disk(percent=self.utilization['disk_percent'])

    def net_io_counters(self):
        disk = collections.namedtuple('Net', 'bytes_sent bytes_recv')
        return disk(
            bytes_sent=self.utilization['bytes_sent'],
            bytes_recv=self.utilization['bytes_received'],
        )
