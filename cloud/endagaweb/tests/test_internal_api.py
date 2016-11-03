"""Tests of the internal API.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import urlparse

from django.test import Client
from django.test import TestCase

from endagaweb import models


class InternalAPITest(TestCase):
    """Tests of the internal API."""

    @classmethod
    def setUpClass(cls):
        """Generate a User, BTS and Number."""
        cls.email = "test@endaga.com"
        cls.user = models.User(username=cls.email, email=cls.email)
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.uuid = "59216199-d664-4b7a-a2db-6f26e9a5d209"
        cls.inbound_url = "http://localhost:8090"
        cls.name = "testtower1"
        cls.bts = models.BTS(
            uuid=cls.uuid, nickname=cls.name, inbound_url=cls.inbound_url,
            network=cls.user_profile.network)
        cls.bts.save()
        cls.uuid2 = "59216197-d664-4b7a-a2db-6f26e9a5d204"
        cls.bts2 = models.BTS(
            uuid=cls.uuid2, nickname='bts2', network=cls.user_profile.network,
            inbound_url='http://localhost:8091')
        cls.bts2.save()
        imsi = "IMSI999990010000000"
        cls.sub = models.Subscriber(balance=10000, name='sub-two', imsi=imsi,
                                    network=cls.bts.network, bts=cls.bts)
        cls.sub.save()
        cls.num = 6285574719464
        cls.kind = "number.nexmo.monthly"
        cls.number = models.Number(
            number=cls.num, state="inuse", network=cls.user_profile.network,
            kind=cls.kind, subscriber=cls.sub)
        cls.number.save()

        # Whitelisted
        cls.email2 = "test2@endaga.com"
        cls.user2 = models.User(username=cls.email2, email=cls.email2)
        cls.user2.save()
        cls.user_profile2 = models.UserProfile.objects.get(user=cls.user2)
        cls.user_profile2.network.bypass_gateway_auth = True
        cls.user_profile2.network.save()
        cls.uuid_whitelist = "59216899-d664-4b7a-a2db-6f26e9a5f205"
        cls.bts_whitelist = models.BTS(uuid=cls.uuid_whitelist,
            nickname='bts_whitelist', network=cls.user_profile2.network,
            inbound_url='http://localhost:8091')
        cls.bts_whitelist.save()
        imsi2 = "IMSI999990010000001"
        cls.sub2 = models.Subscriber(balance=10000, name='sub-three', imsi=imsi2,
                  network=cls.user_profile2.network, bts=cls.bts_whitelist)
        cls.sub2.save()
        cls.num2 = 6285574719465
        cls.kind = "number.nexmo.monthly"
        cls.number2 = models.Number(
            number=cls.num2, state="inuse", network=cls.user_profile2.network,
            kind=cls.kind, subscriber=cls.sub2)
        cls.number2.save()

    @classmethod
    def tearDownClass(cls):
        """Drop all the objects we created."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.bts2.delete()
        cls.number.delete()
        cls.sub.delete()

        cls.user2.delete()
        cls.user_profile2.delete()
        cls.bts_whitelist.delete()
        cls.number2.delete()
        cls.sub2.delete()

    def test_number_lookup(self):
        """We can lookup a number."""
        client = Client()
        data = {
            'number': self.num
        }
        response = client.get("/internal/api/v1/number/", data=data)
        response = json.loads(response.content)
        self.assertEqual(response["netloc"],
                         urlparse.urlparse(self.inbound_url).netloc)
        self.assertEqual(response["number"], str(self.num))
        self.assertEqual(response["hostname"],
                         urlparse.urlparse(self.inbound_url).hostname)
        self.assertEqual(response["source"], self.kind)

    def test_number_auth(self):
        """We can verify a number is owned by a user."""
        client = Client()
        data = {
            'number': self.num,
        }
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = client.get("/internal/api/v1/auth/", data=data, **header)
        self.assertEqual(response.status_code, 200)

    def test_number_auth_bad_num(self):
        """We can verify that we can't call out with numbers we don't own."""
        client = Client()
        data = {
            'number': self.num2,
        }
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = client.get("/internal/api/v1/auth/", data=data, **header)
        self.assertEqual(response.status_code, 401)

    def test_number_bad_auth(self):
        """We can verify that a number doesn't belong to a token."""
        client = Client()
        data = {
            'number': self.num,
        }
        header = {
            'HTTP_AUTHORIZATION': 'badtoken'
        }
        response = client.get("/internal/api/v1/auth/", data=data, **header)
        self.assertEqual(response.status_code, 403)

    def test_whitelist_auth(self):
        """We can verify that we can auth from a whitelist and no token."""
        client = Client()
        data = {
            'number': self.num2,
        }
        response = client.get("/internal/api/v1/auth/", data=data)
        self.assertEqual(response.status_code, 200)

    def test_whitelist_auth_bad_num(self):
        """Let's make sure the whitelist isn't a superuser list."""
        client = Client()
        data = {
            'number': self.num,
        }
        response = client.get("/internal/api/v1/auth/", data=data)
        self.assertEqual(response.status_code, 403)
