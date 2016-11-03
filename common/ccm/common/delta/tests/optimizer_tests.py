#!/usr/bin/env python2
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

import copy
import json
from pprint import pprint
import unittest

from ..protocol import DeltaProtocol, DeltaProtocolCtx
from ..optimizer import DeltaCapable, DeltaProtocolOptimizerFactory

from . import test_case


class DeltaOptimizerTest(unittest.TestCase):

    def setUp(self):
        self.server_in = {}
        self.client_in = {}
        self.client_out = {}

    def _reset_test_data(self):
        self.server_in.clear()
        self.client_in.clear()
        self.client_out.clear()

    # Client classes
    class CheckinHandler(object):
        client_ctx = {
            'section1': DeltaProtocolCtx(),
            'section2': DeltaProtocolCtx(),
            'section3': DeltaProtocolCtx(),
        }

        def __init__(self, response, test):
            self._test = test
            self.process(response)

        def process(self, resp_dict):
            for section in resp_dict:
                self._test.client_in[section] = copy.deepcopy(
                    resp_dict[section]
                )

                if section == "section1":
                    self.process_section1(resp_dict[section])
                elif section == "section2":
                    self.process_section2(resp_dict[section])
                elif section == "section3":
                    self.process_section3(resp_dict[section])

        @DeltaCapable(client_ctx['section1'])
        def process_section1(self, data):
            self._test.client_out['section1'] = copy.deepcopy(data)
            return data

        # Section 2 is tested with skip_empty flag, decorated function
        # is not called on empty deltas
        @DeltaCapable(client_ctx['section2'], True)
        def process_section2(self, data):
            self._test.client_out['section2'] = copy.deepcopy(data)
            return data

        @DeltaCapable(client_ctx['section3'])
        def process_section3(self, data):
            self._test.client_out['section3'] = copy.deepcopy(data)
            return data

        @classmethod
        def reset(cls):
            for section in cls.client_ctx.keys():
                cls.client_ctx[section].reset()


    class Interconnect(object):

        def __init__(self, test):
            self._test = test

        def checkin(self, bts_id):
            status = {
                'bts_id': bts_id,
                'usage': {},
                'uptime': {},
                'system_utilization': {},
                DeltaProtocol.CTX_KEY: {
                    'sections': {
                        'section1':
                            DeltaOptimizerTest.CheckinHandler.client_ctx[
                                'section1'].to_proto_dict(),
                        'section2':
                            DeltaOptimizerTest.CheckinHandler.client_ctx[
                                'section2'].to_proto_dict(),
                        'section3':
                            DeltaOptimizerTest.CheckinHandler.client_ctx[
                                'section3'].to_proto_dict()
                    }
                }
            }

            responder = DeltaOptimizerTest.CheckinResponder(self._test)
            resp = responder.process(status)
            resp_str = json.dumps(resp)
            DeltaOptimizerTest.CheckinHandler(json.loads(resp_str), self._test)

    # Server class
    class CheckinResponder(object):

        optimizers = DeltaProtocolOptimizerFactory()

        def __init__(self, test):
            self.client_ctx_sections = {}
            self.handlers = {
                DeltaProtocol.CTX_KEY: self.delta_handler,
                'bts_id': self.set_bts_id
            }
            self._test = test

        def optimize_section(self, section_name, section_data):
            if self.bts_id:
                bts_sect_id = self.bts_id + '_' + section_name
                opimized = self.optimizers.get(bts_sect_id).prepare(
                    DeltaProtocolCtx.create_from_dict(
                        self.client_ctx_sections.get(section_name)
                    ),
                    section_data
                )
                orig_sz = len(json.dumps(section_data))
                new_sz = len(json.dumps(opimized))
                print(
                    'Optimizing %s. '
                    'payload size was: %d, now: %d. %.2f%% reduction' %
                    (section_name,
                     orig_sz,
                     new_sz,
                     100. * (orig_sz - new_sz) / orig_sz)
                )
                return opimized
            return section_data

        def process(self, status):
            resp = {}
            for section in status:
                if section in self.handlers:
                    self.handlers[section](status[section])

            resp['section1'] = self.optimize_section('section1',
                                                     self.gen_section1())
            resp['section2'] = self.optimize_section('section2',
                                                     self.gen_section2())
            resp['section3'] = self.optimize_section('section3',
                                                     self.gen_section3())
            return resp

        def set_bts_id(self, bts_id):
            self.bts_id = bts_id

        def delta_handler(self, delta_ctx):
            self.client_ctx_sections = {}
            if isinstance(delta_ctx, dict) and 'sections' in delta_ctx:
                sections = delta_ctx.get('sections')
                if sections and isinstance(sections, dict):
                    self.client_ctx_sections = sections

        def gen_section1(self):
            return self._test.server_in['section1']

        def gen_section2(self):
            return self._test.server_in['section2']

        def gen_section3(self):
            return self._test.server_in['section3']

    def _run_checkin_sequence(self, bts_id, test_name=''):
        if test_name:
            test_name = '"' + test_name + '" '

        print('\n----- Checkin Test %sStart -----\n' % test_name)

        print('Old data saved on client side:')
        pprint(
            DeltaOptimizerTest.CheckinHandler.client_ctx.get('section2').data
        )
        print('\nNew data to be sent by server:')
        pprint(self.server_in.get('section2'))
        print

        self.Interconnect(self).checkin(bts_id)

        print('\nDelta received by client:')
        pprint(self.client_in.get('section2'))
        print('\nNew data passed to client:')
        pprint(self.client_out.get('section2'))

        print('\n----- Checkin Test %sEnd -----\n' % test_name)

    @staticmethod
    def remove_ctx_and_sort(cfg):
        if cfg and isinstance(cfg, dict):
            if DeltaProtocol.CTX_KEY in cfg:
                cfg = copy.deepcopy(cfg)
                cfg.pop(DeltaProtocol.CTX_KEY)

            DeltaProtocol.sort_lists(cfg)
        return cfg

    def _for_each_section(self, l, r, skip_sections):
        for section in l:
            if section not in skip_sections:
                left = self.remove_ctx_and_sort(l.get(section))
                right = self.remove_ctx_and_sort(r.get(section))
                yield (section, left, right)

    def _assert_equal(self, l, r, skip_sections=set()):
        for (s, left, right) in self._for_each_section(l, r, skip_sections):
            self.assertEqual(
                left, right,
                ("%s: left and right NOT equal: { %s } vs { %s }" %
                 (s, left.keys(), right.keys()))
            )

    def _assert_not_equal(self, l, r, skip_sections=set()):
        for (s, left, right) in self._for_each_section(l, r, skip_sections):
            self.assertNotEqual(
                left, right,
                ("%s: left and right ARE equal. keys = %s" %
                 (s, left.keys()))
            )

    def _first_time_testcase(self):
        self._reset_test_data()
        # since this is always the first part of each step, it's a good
        # place to ensure per-class shared state is clean
        self.CheckinHandler.reset()
        self.CheckinResponder.optimizers.clear()
        test_cases = test_case.setUpTestCases()
        self.server_in['section1'] = test_cases.old_simple_dict
        self.server_in['section2'] = test_cases.old_deep_dict
        self.server_in['section3'] = test_cases.prod_test_old

        # check that client_ctx is initially empty
        for section in self.CheckinHandler.client_ctx:
            ctx = self.CheckinHandler.client_ctx[section]
            self.assertFalse(ctx.is_valid(), "ctx = %s" % (ctx, ))

        self._run_checkin_sequence('abcdefg123', 'First Time')

        self._assert_equal(self.server_in,
                           self.client_in)

        for section in self.client_in:
            # make sure old clients won't get unexpected delta items
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_in[section]
            ))
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_out[section]
            ))
            self.assertFalse(DeltaProtocol.is_delta(
                self.client_in[section]
            ))
            self.assertTrue(
                self.CheckinHandler.client_ctx[section]
            )

        self._assert_equal(self.server_in,
                           self.client_out)

    def _second_time_testcase_empty_deltas(self):
        self._reset_test_data()
        test_cases = test_case.setUpTestCases()
        self.server_in['section1'] = test_cases.old_simple_dict
        self.server_in['section2'] = test_cases.old_deep_dict
        self.server_in['section3'] = test_cases.prod_test_old

        self._run_checkin_sequence('abcdefg123', 'Second Time No Deltas')

        self._assert_not_equal(self.server_in,
                               self.client_in)

        for section in self.client_in:
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_in[section]
            ))
            self.assertTrue(DeltaProtocol.is_delta(
                self.client_in[section]
            ))

        for section in self.client_out:
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_out[section]
            ))
            self.assertFalse(DeltaProtocol.is_delta(
                self.client_out[section]
            ))

        self._assert_equal(self.server_in,
                           self.client_out, {'section2'})

        self.assertTrue('section2' in self.client_in)
        self.assertFalse('section2' in self.client_out)

    def _deltas_testcase(self):
        self._reset_test_data()
        test_cases = test_case.setUpTestCases()
        self.server_in['section1'] = test_cases.new_simple_dict
        self.server_in['section2'] = test_cases.new_deep_dict
        self.server_in['section3'] = test_cases.prod_test_new

        self._run_checkin_sequence('abcdefg123', 'Delta Optimize')

        self._assert_not_equal(self.server_in,
                               self.client_in)

        for section in self.client_in:
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_in[section]
            ))
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_out[section]
            ))
            self.assertTrue(DeltaProtocol.is_delta(
                self.client_in[section]
            ))

        self._assert_equal(self.server_in,
                           self.client_out)

    def _lost_server_states_no_change_in_data_testcase(self):
        # This test deletes all server side delta states and stimulates
        # no change in data on sever side. It models BTS connection to a
        # new cloud server when there is no change in BTS section data.
        self._reset_test_data()
        test_cases = test_case.setUpTestCases()
        # delete all server CTXs
        self.CheckinResponder.optimizers.clear()

        self.server_in['section1'] = test_cases.new_simple_dict
        self.server_in['section2'] = test_cases.new_deep_dict
        self.server_in['section3'] = test_cases.prod_test_new

        self._run_checkin_sequence('abcdefg123',
                                   'No Prior Sever State, No Changes')

        self._assert_not_equal(self.server_in,
                               self.client_in)

        for section in self.client_in:
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_in[section]
            ))
            self.assertTrue(DeltaProtocol.is_delta(
                self.client_in[section]
            ))

        for section in self.client_out:
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_out[section]
            ))
            self.assertFalse(DeltaProtocol.is_delta(
                self.client_out[section]
            ))

        self._assert_equal(self.server_in,
                           self.client_out, {'section2'})

        self.assertTrue('section2' in self.client_in)
        self.assertFalse('section2' in self.client_out)

    def _lost_server_states_and_changes_in_data_testcase(self):
        # This test deletes all server side delta states and stimulates
        # changes in data on sever side. It models BTS connection to a
        # new cloud server when there is a change in BTS section data.
        self._reset_test_data()
        test_cases = test_case.setUpTestCases()
        # delete all server CTXs
        self.CheckinResponder.optimizers.clear()

        self.server_in['section1'] = test_cases.old_simple_dict
        self.server_in['section2'] = test_cases.old_deep_dict
        self.server_in['section3'] = test_cases.prod_test_old

        self._run_checkin_sequence('abcdefg123',
                                   'No Prior Server State & Changes')

        self._assert_equal(self.server_in,
                           self.client_in)

        for section in self.client_in:
            self.assertTrue(DeltaProtocol.find_delta_capable_ctx(
                self.client_in[section]
            ))
            self.assertFalse(DeltaProtocol.is_delta(
                self.client_in[section]
            ))
            self.assertFalse(DeltaProtocol.find_delta_capable_ctx(
                self.client_out[section]
            ))
            self.assertFalse(DeltaProtocol.is_delta(
                self.client_out[section]
            ))

        self._assert_equal(self.server_in,
                           self.client_out)

    def test_first(self):
        self._first_time_testcase()

    def test_second(self):
        self._first_time_testcase()
        # second_time_testcase must be run after first_time
        self._second_time_testcase_empty_deltas()

    def test_deltas(self):
        self._first_time_testcase()
        self._second_time_testcase_empty_deltas()
        # deltas_testcase must be run after second_time
        self._deltas_testcase()

    def test_lost_server_states(self):
        self._first_time_testcase()
        self._second_time_testcase_empty_deltas()
        self._deltas_testcase()
        # lost_server_states_no_change must be run after deltas
        self._lost_server_states_no_change_in_data_testcase()

    def test_lost_server_states_and_data(self):
        self._first_time_testcase()
        self._second_time_testcase_empty_deltas()
        self._deltas_testcase()
        # lost_server_states_and_changes must be run after deltas
        self._lost_server_states_and_changes_in_data_testcase()

if __name__ == '__main__':
    unittest.main()
