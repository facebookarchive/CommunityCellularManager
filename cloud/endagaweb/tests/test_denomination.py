"""Tests for models.Users.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from django import test
from django.test import TestCase

from endagaweb import models


class TestBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.username = 'y'
        cls.password = 'pw'
        cls.user = models.User(username=cls.username, email='y@l.com')
        cls.user.set_password(cls.password)
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)

        cls.uuid = "59216199-d664-4b7a-a2db-6f26e9a5d208"

        # Create a test client.
        cls.client = test.Client()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.user_profile.delete()

    def tearDown(self):
        self.logout()

    def login(self):
        """Log the client in."""
        data = {
            'email': self.username,
            'password': self.password,
        }
        self.client.post('/auth/', data)

    def logout(self):
        """Log the client out."""
        self.client.get('/logout')


class DenominationUITest(TestBase):
    """Testing that we can add User in the UI."""

    def test_add_denominaton(self):
        self.logout()
        response = self.client.get('/dashboard/network/denominations')
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_add_denominaton_auth(self):
        self.login()
        response = self.client.get('/dashboard/network/denominations')
        self.assertEqual(200, response.status_code)

    def test_delete_denominaton(self):
        self.logout()
        response = self.client.delete('/dashboard/network/denominations')
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_delete_denominaton_auth(self):
        self.login()
        response = self.client.delete('/dashboard/network/denominations')
        self.assertEqual(200, response.status_code)

    def test_post_add_denominaton(self):
        self.logout()
        data = {}
        response = self.client.post('/dashboard/network/denominations', data)
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_post_add_denominaton_auth(self):
        self.login()
        data = {
            'start_amount': 1,
            'end_amount': 2,
            'validity_days': 3
        }
        response = self.client.post('/dashboard/network/denominations', data)
        self.assertEqual(302, response.status_code)
