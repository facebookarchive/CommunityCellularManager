"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import division
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import print_function

from pprint import pprint
import unittest

from .. import dictdiff
from ..protocol import DeltaProtocol
from . import test_case

class DictDiffTestCase(unittest.TestCase):

    def test_basic(self):
        delta = dictdiff.diff(self.new_simple_dict, self.old_simple_dict)
        print("\nOld: ")
        pprint(self.old_simple_dict)
        print("New: ")
        pprint(self.new_simple_dict)
        print("Delta: ")
        pprint(delta)
        new = dictdiff.apply_delta(self.old_simple_dict.copy(), delta)
        print("Result: ")
        pprint(new)
        self.assertEqual(self.new_simple_dict, new)

    def test_deep(self):
        delta = dictdiff.diff(self.new_deep_dict, self.old_deep_dict)
        print("Delta: ")
        pprint(delta)
        new = dictdiff.apply_delta(self.old_deep_dict.copy(), delta)
        # we have to sort lists for comparison to work
        new['dd']['a2']['lst'].sort(key=lambda x: str(x))
        self.assertEqual(self.new_deep_dict, new)

    def test_prod(self):
        self.assertNotEqual(self.prod_test_new, self.prod_test_old)
        delta = dictdiff.diff(self.prod_test_new, self.prod_test_old)
        new = dictdiff.apply_delta(self.prod_test_old.copy(), delta)
        DeltaProtocol.sort_lists(new)
        self.assertEqual(self.prod_test_new, new)

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
