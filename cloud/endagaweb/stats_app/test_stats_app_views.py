"""Testing the stats_app's endpoints.

Usage:
    $ python manage.py test endagaweb.StatsAPITest


Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import urllib

from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from endagaweb import models


# See endagaweb.stats_app.views for notes on this date.
JUN30_2014 = 1406680050


class StatsAPITest(APITestCase):
    """Testing the stats endpoints."""

    @classmethod
    def setUpClass(cls):
        # Setup a user and user profile.
        cls.username = "hal"
        cls.password = "testpw"
        email = "hal@endaga.com"
        cls.user = models.User(username=cls.username, email=email)
        cls.user.set_password(cls.password)
        cls.user.save()
        user_profile = models.UserProfile.objects.get(user=cls.user)  # noqa: F841 T25377293 Grandfathered in
        # TODO(matt): need to link UserProfile and Network?
        # Setup a network.
        network_name = 'test-network-name'
        cls.network = models.Network(name=network_name)
        cls.network.save()
        # Setup a BTS.
        cls.bts = models.BTS(network=cls.network)
        cls.bts.save()
        # Setup a DRF API client and a target endpoint.
        cls.api_client = APIClient()
        cls.endpoint = '/api/v1/stats'

    @classmethod
    def tearDownClass(cls):
        cls.bts.delete()
        cls.network.delete()
        cls.user.delete()

    def setUp(self):
        """Login -- one test logs out, so this cannot be in setUpClass."""
        self.api_client.login(username=self.username, password=self.password)

    def test_get_sans_auth_sans_token(self):
        """Rejected sans auth and sans token."""
        self.api_client.logout()
        level = 'global'
        url = '%s/%s' % (self.endpoint, level)
        response = self.api_client.get(url)
        self.assertEqual(403, response.status_code)

    def test_get_with_auth(self):
        """Access granted if we're logged in like normal."""
        level = 'global'
        url = '%s/%s' % (self.endpoint, level)
        response = self.api_client.get(url)
        self.assertEqual(200, response.status_code)

    def test_query_defaults(self):
        """If params aren't specified in the query, we have defaults."""
        level = 'network'
        params = {}
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        echo = response_content['request']
        expected_start_time = JUN30_2014
        expected_end_time = -1
        expected_interval = 'months'
        expected_stat_type = 'sms'
        expected_level_id = -1
        expected_aggregation = 'count'
        self.assertEqual(expected_start_time, echo['start-time-epoch'])
        self.assertEqual(expected_end_time, echo['end-time-epoch'])
        self.assertEqual(expected_interval, echo['interval'])
        self.assertEqual(expected_stat_type, echo['stat-types'])
        self.assertEqual(expected_level_id, echo['level-id'])
        self.assertEqual(expected_aggregation, echo['aggregation'])

    def test_query_with_params(self):
        """If query params are specified, we'll try to use them."""
        level = 'network'
        params = {
            'start-time-epoch': JUN30_2014,
            'end-time-epoch': JUN30_2014 + 24 * 60 * 60,
            'interval': 'days',
            'stat-types': 'free_sms',
            'level-id': 4,
            'aggregation': 'duration',
        }
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        # Request data should also be echoed back.
        echo = response_content['request']
        self.assertEqual(params['start-time-epoch'], echo['start-time-epoch'])
        self.assertEqual(params['end-time-epoch'], echo['end-time-epoch'])
        self.assertEqual(params['interval'], echo['interval'])
        self.assertEqual(params['stat-types'], echo['stat-types'])
        self.assertEqual(params['level-id'], echo['level-id'])
        self.assertEqual(params['aggregation'], echo['aggregation'])

    def test_response_data_types(self):
        """Response data should be suitable for the NVD3 charting lib.

        We expect something of this form:
            [
                {
                    "key": "free_sms",
                    "values": [
                        [1423686415000, 5]
                        [1423686416000, 24]
                    ]
                }
            ]
        Where timestamps are in milliseconds.
        """
        level = 'network'
        params = {
            'level-id': int(self.network.id)
        }
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        results = response_content['results']
        self.assertTrue(isinstance(results, list))
        self.assertTrue(isinstance(results[0], dict))
        self.assertEqual('sms', results[0]['key'])
        self.assertTrue(isinstance(results[0]['values'], list))
        self.assertTrue(isinstance(results[0]['values'][0], list))
        self.assertTrue(isinstance(results[0]['values'][0][0], int))

    def test_query_with_multiple_stats(self):
        """We can request multiple stat types."""
        level = 'network'
        stat_types = ['free_sms', 'local_sms', 'outside_sms']
        params = {
            'level-id': int(self.network.id),
            'stat-types': ','.join(stat_types),
        }
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        keys = [stat_type['key'] for stat_type in response_content['results']]
        self.assertSetEqual(set(stat_types), set(keys))

    def test_query_with_invalid_interval(self):
        """Asking for an invalid interval should return the default."""
        level = 'global'
        params = {
            'interval': 'millenia'
        }
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        echo = response_content['request']
        self.assertEqual('months', echo['interval'])

    def test_query_with_invalid_stat_type(self):
        """Asking for an invalid stat type should return the default."""
        level = 'global'
        params = {
            'stat-types': 'incoming_data'
        }
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        echo = response_content['request']
        self.assertEqual('sms', echo['stat-types'])

    def test_query_with_invalid_aggregation(self):
        """Asking for an invalid aggregation should return the default."""
        level = 'global'
        params = {
            'aggregation': 'variance'
        }
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        echo = response_content['request']
        self.assertEqual('count', echo['aggregation'])

    def test_query_with_end_time_before_start_time(self):
        """Asking for an invalid start-end range should return the default."""
        level = 'global'
        params = {
            'start-time-epoch': int(JUN30_2014 + 1e3),
            'end-time-epoch': JUN30_2014
        }
        url = '%s/%s?%s' % (self.endpoint, level, urllib.urlencode(params))
        response_content = json.loads(self.api_client.get(url).content)
        echo = response_content['request']
        self.assertEqual(JUN30_2014, echo['start-time-epoch'])
        self.assertEqual(-1, echo['end-time-epoch'])
