"""Tests for the dashboard UI.

Verifying that we can GET and POST to various pages.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import json
import mock
import uuid

from django import test

from endagaweb import models
from endagaweb.views import towers
from endagaweb.templatetags import apptags


class TowerUITest(test.TestCase):
    """Testing that we can add BTS (towers) in the UI."""

    @classmethod
    def setUpClass(cls):
        cls.username = 'y'
        cls.password = 'pw'
        cls.user = models.User(username=cls.username, email='y@l.com')
        cls.user.set_password(cls.password)
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.uuid = "59216199-d664-4b7a-a2db-6f26e9a5d208"
        inbound_url = "http://localhost:8090"
        cls.bts = models.BTS(
            uuid=cls.uuid, nickname='test-name', inbound_url=inbound_url,
            network=cls.user_profile.network)
        cls.bts.save()
        cls.primary_network = cls.user_profile.network
        cls.secondary_network = models.Network.objects.create()
        # Create a test client.
        cls.client = test.Client()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.primary_network.delete()
        cls.secondary_network.delete()

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

    def test_get_towers_sans_auth(self):
        self.logout()
        response = self.client.get('/dashboard/towers')
        # Unlike other routes, we don't redirect to the login page with the
        # next parameter set.  This is because these are DRF routes and it's
        # not clear how to setup that redirect functionality for DRF views.
        self.assertEqual(403, response.status_code)

    def test_get_tower_info_sans_auth(self):
        self.logout()
        response = self.client.get('/dashboard/towers/%s' % self.uuid)
        self.assertEqual(302, response.status_code)

    def test_get_tower_edit_sans_auth(self):
        self.logout()
        response = self.client.get('/dashboard/towers/%s/edit' % self.uuid)
        self.assertEqual(403, response.status_code)

    def test_get_towers_with_auth(self):
        self.login()
        response = self.client.get('/dashboard/towers')
        self.assertEqual(200, response.status_code)

    def test_get_tower_info_with_auth(self):
        self.login()
        response = self.client.get('/dashboard/towers/%s' % self.uuid)
        self.assertEqual(200, response.status_code)

    def test_get_tower_edit_with_auth(self):
        self.login()
        response = self.client.get('/dashboard/towers/%s/edit' % self.uuid)
        self.assertEqual(200, response.status_code)

    def test_add_tower(self):
        """We can create a tower by POSTing to /dashboard/towers."""
        self.login()
        # We should start with just one tower.
        self.assertEqual(1, models.BTS.objects.filter(
            network=self.user_profile.network).count())
        data = {
            'uuid': '59216199-d664-4b7a-a2db-6f26e9a5d300',
            'name': 'test-tower-2',
        }
        self.client.post('/dashboard/towers', data)
        self.assertEqual(2, models.BTS.objects.filter(
            network=self.user_profile.network).count())

    def test_successful_add_tower_response(self):
        """When add tower succeeds, we send 'ok' and add a message."""
        self.login()
        data = {
            'uuid': '69216199-d664-4b7a-a2db-6f26e9a5d300',
            'name': 'test-tower-3',
        }
        response = self.client.post('/dashboard/towers', data)
        # We'll get back JSON (the page reload will be triggered in js).
        expected_response = {
            'status': 'ok',
            'messages': [],
        }
        self.assertEqual(expected_response, json.loads(response.content))

    def test_failed_add_tower_response(self):
        """When add tower fails, we send 'failed' and some messages.

        Note that unlike in the successful case, if add tower fails we send
        messages back as json and render them with jquery.
        """
        self.login()
        data = {
            'uuid': '',
        }
        response = self.client.post('/dashboard/towers', data)
        # We'll get back only JSON.
        expected_response = {
            'status': 'failed',
            'messages': [
                'Invalid UUID.',
            ]
        }
        self.assertEqual(expected_response, json.loads(response.content))

    def test_add_tower_invalid_latitude(self):
        """When we send an invalid latitude, things fail."""
        self.login()
        data = {
            'uuid': '79216199-d664-4b7a-a2db-6f26e9a5d300',
            'name': 'test-tower-4',
            'latitude': 'invalid-lat',
        }
        response = self.client.post('/dashboard/towers', data)
        # We'll get back JSON.
        self.assertEqual('failed', json.loads(response.content)['status'])

    def test_add_tower_invalid_longitude(self):
        """When we send an invalid longitude, things fail."""
        self.login()
        data = {
            'uuid': '89216199-d664-4b7a-a2db-6f26e9a5d300',
            'name': 'test-tower-5',
            'longitude': 'invalid-lon',
        }
        response = self.client.post('/dashboard/towers', data)
        # We'll get back JSON.
        self.assertEqual('failed', json.loads(response.content)['status'])

    def test_edit_tower(self):
        """We can edit tower data by POSTing to /dashboard/towers/<uuid>."""
        self.login()
        data = {
            'nickname': 'new name!',
            'latitude': 24.2,
            'longitude': -73.5,
        }
        url = '/dashboard/towers/%s/edit' % self.uuid
        self.client.post(url, data)
        # Fetch the BTS from the DB and verify its attributes have changed.
        tower = models.BTS.objects.get(uuid=self.uuid)
        self.assertEqual(data['nickname'], tower.nickname)
        self.assertEqual(data['latitude'], float(tower.latitude))
        self.assertEqual(data['longitude'], float(tower.longitude))

    def test_switch_network_fails_sans_access(self):
        """Trying to switch to a network you don't have permission on will fail."""
        self.login()
        response = self.client.get('/dashboard/network/select/%s' % self.secondary_network.pk)
        self.assertEqual(401, response.status_code)
        self.user_profile.refresh_from_db()
        self.assertEqual(self.primary_network, self.user_profile.network)

    def test_switch_network_fails_not_exists(self):
        """Trying to switch to a network that doesn't exist will fail."""
        self.login()
        response = self.client.get('/dashboard/network/select/1337')
        self.assertEqual(400, response.status_code)
        self.user_profile.refresh_from_db()
        self.assertEqual(self.primary_network, self.user_profile.network)

    def test_switch_network(self):
        """Switching to a network should work if you have permission."""
        self.login()
        self.secondary_network.auth_group.user_set.add(self.user_profile.user)
        response = self.client.get('/dashboard/network/select/%s' % self.secondary_network.pk)
        self.assertEqual(302, response.status_code)
        self.user_profile.refresh_from_db()
        self.assertEqual(self.secondary_network, self.user_profile.network)
        self.user_profile.network = self.primary_network
        self.secondary_network.auth_group.user_set.remove(self.user_profile.user)

    def test_network_revoke(self):
        """If you are revoked from a network, you should still default to yours."""
        self.login()
        self.secondary_network.auth_group.user_set.add(self.user_profile.user)
        response = self.client.get('/dashboard/network/select/%s' % self.secondary_network.pk)
        self.assertEqual(302, response.status_code)
        self.user_profile.refresh_from_db()
        self.assertEqual(self.secondary_network, self.user_profile.network)

        self.secondary_network.auth_group.user_set.remove(self.user_profile.user)
        response = self.client.get('/dashboard')
        self.assertEqual(200, response.status_code)
        self.user_profile.refresh_from_db()
        self.assertEqual(self.primary_network, self.user_profile.network)

    def test_no_network_error(self):
        """If you have no networks, you should get an error"""
        self.login()
        self.primary_network.auth_group.user_set.remove(self.user_profile.user)
        response = self.client.get('/dashboard')
        self.assertEqual(401, response.status_code)
        self.primary_network.auth_group.user_set.add(self.user_profile.user)


class ValidateUUIDTest(test.TestCase):
    """Testing endagaweb.views.towers.validate_uuid.

    We'll use assertEqual instead of assertTrue to make sure we actually get
    boolean values and not just Falsey or Truthy values.
    """

    def test_random_string(self):
        value = 'abcdefg'
        self.assertEqual(False, towers.validate_uuid(value))

    def test_int(self):
        value = 1
        self.assertEqual(False, towers.validate_uuid(value))

    def test_uuid(self):
        value = str(uuid.uuid4())
        self.assertEqual(True, towers.validate_uuid(value))

    def test_upper_case_uuid(self):
        value = str(uuid.uuid4()).upper()
        self.assertEqual(True, towers.validate_uuid(value))

class TemplateTagTest(test.TestCase):
    """
    Testing template tags
    """
    def test_timezone_offset_dst_transition(self):
        tz = 'US/Eastern'
        # this is a non-existent time, due to a DST transition
        fake_date = datetime.datetime(2002, 4, 7, 2, 30)
        orig_datetime = datetime.datetime
        datetime.datetime = mock.Mock()
        datetime.datetime.now.return_value = fake_date
        #eastern is normally -5, but DST moves it to -4
        self.assertEqual("%s (UTC-4:00)" % tz, apptags.timezone_offset(tz))
        datetime.datetime = orig_datetime

