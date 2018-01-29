"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from unittest import TestCase

from .. import base

class GCounterTestCase(TestCase):
    def setUp(self):
        self.g = base.GCounter("g1")
        self.g2 = base.GCounter("g2")

    def test_increment(self):
        self.g.increment()
        self.assertEqual(self.g.value(), 1)

    def test_merge(self):
        self.g.increment(100)
        self.g2.increment(200)
        self.assertEqual(self.g.value(), 100)
        self.assertEqual(self.g2.value(), 200)
        g3 = base.GCounter.merge(self.g, self.g2, "g3")
        self.assertEqual(g3.value(), 300)
        g3.increment(10)
        self.assertEqual(g3.value(), 310)

    def test_from_state(self):
        state = {'g4': 4, 'g5': 5}
        g = base.GCounter.from_state(state, name="gtest")
        self.assertEqual(g.value(), 9)
        self.assertEqual(g.name, "gtest")

    def test_from_invalid_state(self):
        # note, this is a valid PNCounter state
        state = {'p': {'pn4': 4, 'pn5': 5}, 'n': {'pn6': 6, 'pn5': 5}}
        with self.assertRaises(ValueError):
            g = base.GCounter.from_state(state, name="test")
        state = 1
        with self.assertRaises(ValueError):
            g = base.GCounter.from_state(state, name="test")  # noqa: F841 T25377293 Grandfathered in

    def test_is_used(self):
        self.assertFalse(self.g.is_used())
        self.g.increment()
        self.assertTrue(self.g.is_used())

class PNCounterTestCase(TestCase):
    def setUp(self):
        self.pn = base.PNCounter("pn1")
        self.pn2 = base.PNCounter("pn2")

    def test_increment(self):
        self.pn.increment()
        self.assertEqual(self.pn.value(), 1)

    def test_decrement(self):
        self.pn.decrement()
        self.assertEqual(self.pn.value(), -1)

    def test_merge(self):
        self.pn.decrement(100)
        self.pn2.increment(200)
        self.assertEqual(self.pn.value(), -100)
        self.assertEqual(self.pn2.value(), 200)
        pn3 = base.PNCounter.merge(self.pn, self.pn2, "pn3")
        self.assertEqual(pn3.value(), 100)
        self.assertEqual(pn3.name, "pn3")
        pn3.increment(10)
        self.assertEqual(pn3.value(), 110)

    def test_from_state(self):
        state = {'p': {'pn4': 4, 'pn5': 5}, 'n': {'pn6': 6, 'pn5': 5}}
        pn = base.PNCounter.from_state(state, name="pntest")
        self.assertEqual(pn.value(), -2)
        self.assertEqual(pn.P.value(), 9)
        self.assertEqual(pn.N.value(), 11)
        self.assertEqual(pn.name, "pntest")
        self.assertEqual(pn.P.name, "pntest")
        self.assertEqual(pn.N.name, "pntest")

    def test_from_invalid_state(self):
        state = {'p': {'pn4': 4, 'pn5': 5}}
        with self.assertRaises(ValueError):
            pn = base.PNCounter.from_state(state)
        state = {'a': 1, 'b': 2}
        with self.assertRaises(ValueError):
            pn = base.PNCounter.from_state(state)  # noqa: F841 T25377293 Grandfathered in

    def test_is_used(self):
        self.assertFalse(self.pn.is_used())
        self.pn.increment()
        self.assertTrue(self.pn.is_used())
        self.pn.decrement()
        self.assertTrue(self.pn.is_used())
