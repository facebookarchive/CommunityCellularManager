"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""
import mock

from django.test import TestCase
from django.test import Client
from django.contrib.gis.geos import Point

from endagaweb import models
from endagaweb import notifications

class SasonTest(TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Using setUpClass so we don't create duplicate objects."""
        cls.user = models.User(username="zzz", email="z@e.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        # mock out notifications' celery
        cls.old_celery_app = notifications.celery_app
        notifications.celery_app = mock.MagicMock()
        cls.lat = 37.871783 
        cls.lng = -122.260931 #berkeley

        #3 bts's non overlapping in channel, overlapping in location
        cls.bts1 = models.BTS(uuid="1", nickname="test-bts-1",
                              inbound_url="http://localhost/224466/test",
                              network=cls.user_profile.network, band="GSM900",
                              channel=1, location=Point(cls.lng,cls.lat),
                              power_level=100)
        cls.bts1.save()

        cls.bts2 = models.BTS(uuid="2", nickname="test-bts-2",
                              inbound_url="http://localhost/224466/test",
                              network=cls.user_profile.network, band="GSM900",
                              channel=3, location=Point(cls.lng,cls.lat),
                              power_level=100)
        cls.bts2.save()

        cls.bts3 = models.BTS(uuid="3", nickname="test-bts-3",
                              inbound_url="http://localhost/224466/test",
                              network=cls.user_profile.network, band="GSM900",
                              channel=5, location=Point(cls.lng,cls.lat),
                              power_level=100)
        cls.bts3.save()

    
    @classmethod
    def tearDownClass(cls):
        """Delete some of the things we created."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts1.delete()
        cls.bts2.delete()
        cls.bts3.delete()
        notifications.celery_app = cls.old_celery_app

    def setUp(self):
        self.client = Client()

    def getUnusedChannel(self, band):
        return models.BTS.bands[band]['valid_values'].difference(set([self.bts1.channel,
                                                                      self.bts2.channel,
                                                                      self.bts3.channel])).pop()
        
    def test_ping_get_success(self):
        url = '/sason/ping/'
        response = self.client.get(url, {})
        self.assertEqual(200, response.status_code)

    def test_ping_post_fail(self):
        url = '/sason/ping/'
        response = self.client.post(url, {})
        self.assertEqual(405, response.status_code)

    def test_acquire_success(self):
        url = '/sason/acquire/'
        data = {
            'uuid': self.bts1.uuid,
            'lat': self.lat,
            'long': self.lng,
            'band': self.bts1.band,
            'channel': self.getUnusedChannel(self.bts1.band),
            'power_level' : self.bts1.power_level
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(200, resp.status_code)

    def test_acquire_contention(self):
        url = '/sason/acquire/'
        data = {
            'uuid': self.bts1.uuid,
            'lat': self.lat,
            'long': self.lng,
            'band': self.bts1.band,
            'channel': self.bts2.channel, #conflict!
            'power_level' : self.bts1.power_level
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(409, resp.status_code)

    def test_acquire_move_success(self):
        url = '/sason/acquire/'
        data = {
            'uuid': self.bts1.uuid,
            'lat': 10.0, #somewhere else
            'long': 10.0,
            'band': self.bts1.band,
            'channel': self.bts2.channel, #no more conflict!
            'power_level' : self.bts1.power_level
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(200, resp.status_code)

    def test_acquire_missing_args(self):
        url = '/sason/acquire/'
        data = {
            'lat': self.lat,
            'long': self.lng,
            'band': self.bts1.band,
            'channel': self.getUnusedChannel(self.bts1.band),
            'power_level' : self.bts1.power_level
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(406, resp.status_code)

    def test_acquire_bad_args(self):
        url = '/sason/acquire/'
        data = {
            'uuid': self.bts1.uuid,
            'lat': self.lat,
            'long': self.lng,
            'band': "GSM800",  #bad band
            'channel': self.getUnusedChannel(self.bts1.band),
            'power_level' : self.bts1.power_level
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(400, resp.status_code)

    def test_acquire_get_fail(self):
        url = '/sason/acquire/'
        response = self.client.get(url, {})
        self.assertEqual(405, response.status_code)

    def test_request_success(self):
        url = '/sason/request/'
        data = {
            'uuid': self.bts1.uuid,
            'lat': self.lat,
            'long': self.lng,
            'bands': self.bts1.band + ",GSM850",
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(
            resp.data[self.bts1.band],
            models.BTS.bands[self.bts1.band]['valid_values'].difference(
                set([self.bts2.channel,
                     self.bts3.channel])))
        self.assertEqual(200, resp.status_code)

    def test_request_missing_args(self):
        url = '/sason/request/'
        data = {
            'uuid': self.bts1.uuid,
            'lat': self.lat,
            'long': self.lng,
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(406, resp.status_code)

    def test_request_bad_args(self):
        url = '/sason/request/'
        data = {
            'uuid': self.bts1.uuid,
            'lat': self.lat,
            'long': self.lng,
            'bands': self.bts1.band + ",GSM800",
        }
        resp = self.client.post(url, data=data)
        self.assertEqual(400, resp.status_code)
