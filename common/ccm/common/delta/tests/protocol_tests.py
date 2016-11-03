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

import json
import copy
import unittest
from ccm.common.delta import protocol, optimizer
from . import test_case

class DeltaProtocolTestCase(unittest.TestCase):

    def _delta_test(self, new, old):
        test_delta = protocol.DeltaProtocol.make_delta(new, old)
        self.assertTrue(isinstance(test_delta, dict))
        self.assertTrue('+/-' in test_delta)
        self.assertTrue('sig' in test_delta)
        self.assertTrue('alg' in test_delta['sig'])
        self.assertEqual(test_delta['sig']['alg'], 'md5')
        self.assertTrue('old' in test_delta['sig'])

        delta_json = json.dumps(test_delta)
        delta = json.loads(delta_json)

        test_delta['bla'] = 'bla'
        self.assertTrue(protocol.DeltaProtocol.is_delta(delta))
        self.assertFalse(protocol.DeltaProtocol.is_delta(test_delta))

        generated_new, _, _ = protocol.DeltaProtocol.apply_delta(delta, old)
        protocol.DeltaProtocol.sort_lists(new)
        protocol.DeltaProtocol.sort_lists(generated_new)

        self.assertEqual(new, generated_new)

    def test_basic(self):
        self._delta_test(self.new_simple_dict, self.old_simple_dict)

    def test_deep(self):
        self._delta_test(self.new_deep_dict, self.old_deep_dict)

    def test_prod(self):
        self._delta_test(self.prod_test_new, self.prod_test_old)

    def test_protocol_decorator(self):
        ctx = protocol.DeltaProtocolCtx()
        class_ctx = protocol.DeltaProtocolCtx()

        @optimizer.DeltaCapableFunction(ctx)
        def unsuspecting_process_f(test_dict, existing_dict):
            self.assertEqual(test_dict, existing_dict)

        class TestDecoratorClass:
            @optimizer.DeltaCapable(class_ctx)
            def unsuspecting_process_f(myself, test_dict, existing_dict):
                self.assertEqual(test_dict, existing_dict)

        testClasInst = TestDecoratorClass()

        protocol.DeltaProtocol.sort_lists(self.prod_test_old)
        protocol.DeltaProtocol.sort_lists(self.prod_test_new)

        test_dict = copy.deepcopy(self.prod_test_old)
        self.assertTrue(protocol.DeltaProtocol.append_delta_ctx(test_dict))
        unsuspecting_process_f(test_dict, self.prod_test_old)

        test_dict = copy.deepcopy(self.prod_test_old)
        self.assertTrue(protocol.DeltaProtocol.append_delta_ctx(test_dict))
        testClasInst.unsuspecting_process_f(test_dict, self.prod_test_old)

        test_delta = protocol.DeltaProtocol.make_delta(self.prod_test_new,
                                                       self.prod_test_old)

        # print("\nDecorator Test Delta (old to new):")
        # pprint(test_delta)

        unsuspecting_process_f(test_delta, self.prod_test_new)
        testClasInst.unsuspecting_process_f(test_delta, self.prod_test_new)

        test_delta = protocol.DeltaProtocol.make_delta(self.prod_test_old,
                                                       self.prod_test_new)

        unsuspecting_process_f(test_delta, self.prod_test_old)
        testClasInst.unsuspecting_process_f(test_delta, self.prod_test_old)

    def setUp(self):
        test_cases = test_case.setUpTestCases()
        self.old_simple_dict = test_cases.old_simple_dict
        self.new_simple_dict = test_cases.new_simple_dict
        self.old_deep_dict = test_cases.old_deep_dict
        self.new_deep_dict = test_cases.new_deep_dict
        self.prod_test_old = test_cases.prod_test_old
        self.prod_test_new = test_cases.prod_test_new


if __name__ == '__main__':
    unittest.main()
