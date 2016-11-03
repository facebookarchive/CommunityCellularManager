"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from copy import deepcopy
import json
import os


from ccm.common.delta import DeltaProtocol


def setUpTestCases():
    return TestCaseData()


class TestCaseData(object):

    def __init__(self):
        cls = self.__class__
        self.old_simple_dict = deepcopy(cls._old_simple_dict)
        self.new_simple_dict = deepcopy(cls._new_simple_dict)
        self.old_deep_dict = deepcopy(cls._old_deep_dict)
        self.new_deep_dict = deepcopy(cls._new_deep_dict)
        self.prod_test_old = deepcopy(cls._prod_test_old)
        self.prod_test_new = deepcopy(cls._prod_test_new)

    @classmethod
    def initTestData(cls):
        DeltaProtocol.sort_lists(cls._old_deep_dict)
        DeltaProtocol.sort_lists(cls._new_deep_dict)
        SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
        PROD_TEST_JSON_NEW = SCRIPT_PATH + '/endaga_testcase_new.json'
        PROD_TEST_JSON_OLD = SCRIPT_PATH + '/endaga_testcase_old.json'
        with open(PROD_TEST_JSON_OLD, 'r') as f:
            cls._prod_test_old = json.load(f)
        with open(PROD_TEST_JSON_NEW, 'r') as f:
            cls._prod_test_new = json.load(f)
        # sort prod data
        DeltaProtocol.sort_lists(cls._prod_test_old)
        DeltaProtocol.sort_lists(cls._prod_test_new)

    _old_simple_dict = {
        'a': 'aval',
        'b': 123,
        'c': True,
        'd': False,
        'z': 'too remove',
        'l': [1, 3, 5, 8]
    }
    _new_simple_dict = {
        'a': 'aval',
        'b': 1234,
        'c': False,
        'd': False,
        'e': 33,
        'l': [1, 3, 5, 6],
        'l2': ['s', 'i', 'm', 'p', 1, 'e']
    }
    _old_deep_dict = {
        'a': 'aval',
        'b': 123,
        'c': True,
        'd': False,
        'z': 'too remove',
        'prices': [
            {
                "billable_unit": 1,
                "cost_to_subscriber_per_min": 1098000,
                "cost_to_subscriber_per_sms": 14000,
                "country_code": "RE",
                "country_name": u"R\u00E9union Island",
                "directionality": "off_network_send",
                "prefix": "262"
            },
            {
                "billable_unit": 1,
                "cost_to_subscriber_per_min": 1098000,
                "cost_to_subscriber_per_sms": 14000,
                "country_code": "RS",
                "country_name": "Serbia",
                "directionality": "off_network_send",
                "prefix": "381"
            }
        ],
        'dd': {
            'l': [1, 2, 3, 4, 5],
            'a1': 11,
            'a2': {
                'a': 'aaa',
                'y': 321,
                'lst': [11, 2, 13]
            }
        }
    }
    _new_deep_dict = {
        'a': 'aval',
        'b': 1234,
        'c': False,
        'd': False,
        'e': 33,
        'prices': [
            {
                "billable_unit": 1,
                "cost_to_subscriber_per_min": 1098000,
                "cost_to_subscriber_per_sms": 14000,
                "country_code": "RE",
                "country_name": u"R\u00E9union Island",
                "directionality": "off_network_send",
                "prefix": "262"
            },
            {
                "billable_unit": 1,
                "cost_to_subscriber_per_min": 1098000,
                "cost_to_subscriber_per_sms": 14000,
                "country_code": "RS",
                "country_name": "Serbia",
                "directionality": "off_network_send",
                "prefix": "381"
            }
        ],
        'dd': {
            'l': [1, 2, 3, 4, 5],
            'b1': 12,
            'a2': {'a': 'bbb', 'y': 321, 'lst': [11, 12, '13']},
            'b2': {'ccc': True}
        }
    }


TestCaseData.initTestData()
