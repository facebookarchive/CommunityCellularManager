"""Testing registration and checking control at core.registration.

Usage:
    $ nosetests core.tests.registration_tests

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import unittest

from core import registration
from core.tests import mocks


class GetRegistrationConfTest(unittest.TestCase):
    """Testing the get_registration_conf method."""
    def setUp(self):
        pass

    def test_raise_value_error_if_request_fails(self):
        """If the request fails, we should raise."""
        return_code = 500
        registration.requests = mocks.MockRequests(return_code)
        with self.assertRaises(ValueError):
            registration.get_registration_conf()
