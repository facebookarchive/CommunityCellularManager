"""Tests for urls.

Usage:
    $ python manage.py test endagaweb.URLTestCase

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
from django.core.urlresolvers import resolve
from unittest import TestCase

from endagaweb import urls


class URLTestCase(TestCase):
    """Testing the different URLs map to the correct view."""

    def test_staff_login(self):
        """
        Validates that we can access the staff login view
        """
        self.assertEqual(resolve('/staff-login/').func.func_name,
                         'staff_login_view')
