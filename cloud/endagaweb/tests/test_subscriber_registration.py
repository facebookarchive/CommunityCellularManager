"""Testing endagaweb.views.api.Register.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from django import test

from endagaweb import models

class RegisterTest(test.TestCase):
    """Testing the GET and POST handler on the Register API view."""

    @classmethod
    def setUpClass(cls):
        """Using setUpClass so we don't create duplicate objects."""
        # Create a user, user profile, BTS and subscriber.
        cls.user = models.User(username="cam", email="c@e.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.bts = models.BTS(uuid="zyxw9876", nickname="test-bts",
                             inbound_url="http://localhost/inbound-test",
                             network=cls.user_profile.network)
        cls.bts.save()
        cls.subscriber_imsi = 'IMSI000987123456789'
        cls.subscriber = models.Subscriber.objects.create(
            balance=1000, name='cam-test-name', imsi=cls.subscriber_imsi,
            network=cls.bts.network)
        cls.subscriber.save()
        # Register a number with this subscriber.
        cls.subscriber_number = '5559876'
        registered_number = models.Number(
            number=cls.subscriber_number, state='inuse',
            kind='number.nexmo.monthly', subscriber=cls.subscriber)
        registered_number.save()
        # Set the registration endpoint.
        cls.endpoint = '/api/v1/register/'

    @classmethod
    def tearDownClass(cls):
        """Deleting the objects created for the tests."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.subscriber.delete()

    def setUp(self):
        self.client = test.Client()
        # Create an "available" number.
        self.available_number = models.Number(
            number='5554433', state='available', kind='number.nexmo.monthly',
            country_id="US")
        self.available_number.save()

    def tearDown(self):
        self.available_number.delete()

    def test_forbidden_sans_session_auth_and_sans_token_auth(self):
        """Without session auth or token auth, we're denied."""
        response = self.client.get(self.endpoint)
        self.assertEqual(403, response.status_code)
        response = self.client.post(self.endpoint)
        self.assertEqual(403, response.status_code)

    def test_denied_with_bad_token(self):
        """With a bad token, we're denied."""
        token = 'bad-token-123'
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % token
        }
        response = self.client.get(self.endpoint, **header)
        self.assertEqual(403, response.status_code)
        response = self.client.post(self.endpoint, **header)
        self.assertEqual(403, response.status_code)

    def test_access_granted_with_valid_token(self):
        """We can hit the endpoint with a valid token."""
        # TODO(matt): this seems to work, but I guess I'm surprised it's not a
        #             token attached to the BTS, since it's the BTS using this
        #             API.
        token = self.user_profile.network.api_token
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % token
        }
        response = self.client.get(self.endpoint, **header)
        self.assertNotEqual(403, response.status_code)
        response = self.client.post(self.endpoint, **header)
        self.assertNotEqual(403, response.status_code)

    def test_register_new_imsi_get(self):
        """Registering a number with a new IMSI sets up a new subscriber."""
        new_imsi = 'IMSI000555123456789'
        endpoint = self.endpoint + '%s/%s/?imsi=%s' % (
            self.bts.uuid, self.available_number.number, new_imsi)
        token = self.user_profile.network.api_token
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % token
        }
        self.client.get(endpoint, **header)
        # Reload the number.  It should now be "inuse" and associated with the
        # BTS.
        self.available_number = models.Number.objects.get(
            id=self.available_number.id)
        self.assertEqual('inuse', self.available_number.state)
        self.assertEqual(self.user_profile.network,
                         self.available_number.network)
        # And there should now be two subscribers.
        self.assertEqual(2, len(models.Subscriber.objects.all()))
        # Cleanup this new sub as it won't get deleted in tearDownClass.
        models.Subscriber.objects.filter(imsi=new_imsi).delete()

    def test_register_new_imsi_onestep(self):
        """ Registering a number with a new IMSI sets up a new subscriber,
        using the POST endpoint. """
        new_imsi = 'IMSI000555123456789'
        token = self.user_profile.network.api_token
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % token
        }
        data = {'imsi': new_imsi, 'bts_uuid': self.bts.uuid}
        r = self.client.post(self.endpoint, data, **header)  # noqa: F841 T25377293 Grandfathered in
        # Reload the number.  It should now be "inuse" and associated with the
        # BTS.
        self.available_number = models.Number.objects.get(
            id=self.available_number.id)
        self.assertEqual('inuse', self.available_number.state)
        self.assertEqual(self.user_profile.network,
                         self.available_number.network)
        # And there should now be two subscribers.
        self.assertEqual(2, len(models.Subscriber.objects.all()))
        # Cleanup this new sub as it won't get deleted in tearDownClass.
        models.Subscriber.objects.filter(imsi=new_imsi).delete()

    def test_register_with_preexisting_imsi_original_bts(self):
        """Registering a number with a preexisting IMSI on the IMSI's original
        BTS sets up a new number for that IMSI.
        """
        endpoint = self.endpoint + '%s/%s/?imsi=%s' % (
            self.bts.uuid, self.available_number.number, self.subscriber.imsi)
        token = self.user_profile.network.api_token
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % token
        }
        response = self.client.get(endpoint, **header)
        # This request should be 200 A-OK and the subscriber should now have
        # two numbers.
        self.assertEqual(200, response.status_code)
        expected_numbers = [self.subscriber_number,
                            self.available_number.number]
        actual_numbers = self.subscriber.numbers().split(', ')
        self.assertItemsEqual(expected_numbers, actual_numbers)

    def test_register_with_preexisting_imsi_original_bts_post(self):
        """ Registering a number with a preexisting IMSI on the IMSI's original
        BTS returns the SAME number for that IMSI. Note, this is a change in
        behavior from the GET endpoint.
        """
        token = self.user_profile.network.api_token
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % token
        }
        data = {'imsi': self.subscriber.imsi, 'bts_uuid': self.bts.uuid}
        response = self.client.post(self.endpoint, data, **header)
        # This request should be 200 A-OK and the subscriber should now have
        # two numbers.
        self.assertEqual(200, response.status_code)
        expected_numbers = [self.subscriber_number,]
        actual_numbers = self.subscriber.numbers().split(', ')
        self.assertItemsEqual(expected_numbers, actual_numbers)

    def test_register_number_on_another_users_bts(self):
        """Numbers created on one BTS can't be registered on another BTS."""
        # Create a new user and BTS.
        user_two = models.User(username="ryt", email="r@t.com")
        user_two.save()
        user_profile_two = models.UserProfile.objects.get(user=user_two)
        bts_two = models.BTS(uuid="aabb33", nickname="test-bts-two",
                             inbound_url="http://localhost/inbound-test-two",
                             network=user_profile_two.network)
        bts_two.save()
        # Attach the avaiable number to the original BTS.
        self.available_number.bts = self.bts
        self.available_number.save()
        # Try to register the number to the second BTS.
        endpoint = self.endpoint + '%s/%s/?imsi=%s' % (
            bts_two.uuid, self.available_number.number,
            self.subscriber.imsi)
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = self.client.get(endpoint, **header)
        # This request should result in a 403 Not Authorized.  And the sub
        # should still have but one number.
        self.assertEqual(403, response.status_code)
        self.assertEqual(self.subscriber_number, self.subscriber.numbers())
        # Clean up the BTS that was created in this test.
        bts_two.delete()
