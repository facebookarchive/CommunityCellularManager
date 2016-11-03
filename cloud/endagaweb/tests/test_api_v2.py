"""Tests for api_v2 views.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import json

from django.test import Client
from django.test import TestCase
from rest_framework.authtoken.models import Token
import itsdangerous
import mock
import pytz

from endagaweb import models


class NumberTest(TestCase):
    """Testing the Number API view."""

    @classmethod
    def setUpClass(cls):
        cls.password = 'pw'
        cls.user = models.User(username='h', email='h@l.com')
        cls.user.set_password(cls.password)
        cls.user.save()
        cls.user2 = models.User(username='l', email='m@m.com')
        cls.user2.set_password(cls.password)
        cls.user2.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.user_profile2 = models.UserProfile.objects.get(user=cls.user2)
        # Create a BTS for each user profile.
        uuid = "59216199-d664-4b7a-a2db-6f26e9a5d323"
        inbound_url = "http://localhost:8090"
        name = "test-tower-user-one"
        cls.bts = models.BTS(uuid=uuid, nickname=name, inbound_url=inbound_url,
                             secret='ok', network=cls.user_profile.network)
        cls.bts.save()
        uuid = "1eac9487-fc7c-4674-8c38-dab66d612453"
        inbound_url = "http://localhost:8090"
        name = "test-tower-user-two"
        cls.bts2 = models.BTS(uuid=uuid, nickname=name,
                              inbound_url=inbound_url,
                              network=cls.user_profile2.network)
        cls.bts2.save()
        # Create two subscribers, one for each tower, each with a number.
        cls.imsi = "IMSI999990000000555"
        cls.sub = models.Subscriber(
            balance=100000, name='sub-one', imsi=cls.imsi,
            network=cls.bts.network, bts=cls.bts)
        cls.sub.save()
        cls.number = models.Number(number='6285574719324', state="inuse",
                                   network=cls.user_profile.network,
                                   subscriber=cls.sub,
                                   kind="number.nexmo.monthly")
        cls.number.save()
        cls.imsi2 = "IMSI999990000000556"
        cls.sub2 = models.Subscriber(
            balance=100000, name='sub-two', imsi=cls.imsi2,
            network=cls.bts2.network, bts=cls.bts2)
        cls.sub2.save()
        cls.number2 = models.Number(number='6285574719443', state="inuse",
                                    network=cls.user_profile2.network,
                                    subscriber=cls.sub2,
                                    kind="number.nexmo.monthly")
        cls.number2.save()
        # Create one last number, unattached to a subscriber.
        cls.number3 = models.Number(number='5551234', state="available",
                                    kind="number.nexmo.monthly")
        cls.number3.save()

    @classmethod
    def tearDownClass(cls):
        """Destroy the objects we created for the test."""
        cls.user.delete()
        cls.user2.delete()
        cls.user_profile.delete()
        cls.user_profile2.delete()
        cls.bts.delete()
        cls.bts2.delete()
        cls.sub.delete()
        cls.sub2.delete()
        cls.number.delete()
        cls.number2.delete()
        cls.number3.delete()

    def setUp(self):
        self.client = Client()

    def tearDown(self):
        self.logout()

    def login(self, user):
        """Log the client in."""
        data = {
            'email': user.username,
            'password': self.password,
        }
        self.client.post('/auth/', data)

    def logout(self):
        """Log the client out."""
        self.client.get('/logout')

    def test_get(self):
        """GET is not supported."""
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        url = '/api/v2/numbers/%s' % self.number.number
        response = self.client.get(url, **header)
        self.assertEqual(405, response.status_code)

    def test_post_sans_token(self):
        """POST fails without a token."""
        url = '/api/v2/numbers/%s' % self.number.number
        data = {
            'state': 'available'
        }
        header = {}
        response = self.client.post(url, data=data, **header)
        self.assertEqual(403, response.status_code)

    def test_post_wrong_token(self):
        """POST with the wrong token fails."""
        # Try to POST to UserProfile1's number with UP2's API token.
        url = '/api/v2/numbers/%s' % self.number.number
        data = {
            'state': 'available'
        }
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        response = self.client.post(url, data=data, **header)
        self.assertEqual(403, response.status_code)

    def test_post_sans_params(self):
        """POST fails without valid params."""
        url = '/api/v2/numbers/%s' % self.number.number
        data = {}
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = self.client.post(url, data=data, **header)
        self.assertEqual(400, response.status_code)

    def test_post_invalid_state(self):
        """POST fails with invalid state."""
        url = '/api/v2/numbers/%s' % self.number.number
        data = {
            'state': 'invalid'
        }
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = self.client.post(url, data=data, **header)
        self.assertEqual(400, response.status_code)

    def test_deactivate_number(self):
        """We can deactivate one of the Subscriber's numbers via POST.

        Pushes number into the 'available' state and disassociates the number
        from the subscriber.  Starts an async post task (which we will mock).
        Should also create a 'deactivate_number' UsageEvent.
        """
        # This subscriber currently has only one number and deleting the last
        # number is verboten, so first we've gotta add another number.
        new_number = models.Number(number='6285574719987', state="inuse",
                                   network=self.user_profile.network,
                                   subscriber=self.sub,
                                   kind="number.nexmo.monthly")
        new_number.save()
        # Deactivate the original number.
        url = '/api/v2/numbers/%s' % self.number.number
        data = {
            'state': 'available'
        }
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        with mock.patch('endagaweb.tasks.async_post.delay') as mocked_task:
            response = self.client.post(url, data=data, **header)
        self.assertEqual(200, response.status_code)
        # Reload the original number from the db and check its state.
        number = models.Number.objects.get(id=self.number.id)
        self.assertEqual(data['state'], number.state)
        # The subscriber should now have one associated number.  Reload the
        # sub from the db to verify.
        subscriber = models.Subscriber.objects.get(id=self.sub.id)
        self.assertEqual(new_number.number, subscriber.numbers())
        # The original number should not be associated with a Subscriber or a
        # Network.
        self.assertEqual(None, number.subscriber)
        self.assertEqual(None, number.network)
        # The mocked task should have been called with specific arguments
        self.assertTrue(mocked_task.called)
        args, _ = mocked_task.call_args
        task_endpoint, task_data = args
        expected_url = '%s/config/deactivate_number' % self.bts.inbound_url
        self.assertEqual(expected_url, task_endpoint)
        # The task_data should be signed with the BTS UUID and should have a
        # jwt key which is a dict with a number key.
        serializer = itsdangerous.JSONWebSignatureSerializer(self.bts.secret)
        task_data = serializer.loads(task_data['jwt'])
        self.assertEqual(number.number, task_data['number'])
        # A 'deactivate_number' UsageEvent should have been created.
        event = models.UsageEvent.objects.get(to_number=number.number,
                                              kind='deactivate_number')
        self.assertEqual('deactivated phone number: %s' % number.number,
                         event.reason)

    def test_deactivate_last_number(self):
        """Cannot deactivate a subscriber's last number.

        (Should delete the subscriber instead.)
        """
        url = '/api/v2/numbers/%s' % self.number.number
        data = {
            'state': 'available'
        }
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = self.client.post(url, data=data, **header)
        self.assertEqual(400, response.status_code)
        # Reload the number from the db and check its state.
        number = models.Number.objects.get(id=self.number.id)
        self.assertEqual('inuse', number.state)
        # The subscriber should still have one associated number.  Reload the
        # sub from the db to check.
        subscriber = models.Subscriber.objects.get(id=self.sub.id)
        self.assertEqual(number.number, subscriber.numbers())

    def test_release_number_not_staff(self):
        """Only staff can release numbers."""
        self.login(self.user)
        url = '/api/v2/numbers/%s' % self.number3.number
        data = {
            'state': 'released'
        }
        response = self.client.post(url, data=data)
        # The request should fail.
        self.assertEqual(404, response.status_code)

    def test_release_number_in_bad_state(self):
        """Can't release numbers that are inuse."""
        # Promote the user to staff.
        self.user.is_staff = True
        self.user.save()
        self.login(self.user)
        # But drop the number into an inuse state.
        self.number3.state = 'inuse'
        self.number3.save()
        url = '/api/v2/numbers/%s' % self.number3.number
        data = {
            'state': 'released'
        }
        response = self.client.post(url, data=data)
        # The request should fail.
        self.assertEqual(400, response.status_code)

    def test_release_number_still_associated(self):
        """Can't release numbers still attached to subs."""
        # Promote the user to staff.
        self.user.is_staff = True
        self.user.save()
        self.login(self.user)
        # But associate the number with a sub.
        self.number3.subscriber = self.sub
        self.number3.save()
        url = '/api/v2/numbers/%s' % self.number3.number
        data = {
            'state': 'released'
        }
        response = self.client.post(url, data=data)
        # The request should fail.
        self.assertEqual(400, response.status_code)

    def test_release_number(self):
        """We can release an unused number back to Nexmo via POST.

        Deletes numbers, essentially.  The number must be 'available' and
        unassociated with a sub or network.  Will use the Nexmo IC provider to
        cancel the number.
        """
        # Promote the user_profile to staff.
        self.user.is_staff = True
        self.user.save()
        self.login(self.user)
        # Make sure the number is in the right state.
        self.number3.subscriber = None
        self.number3.state = 'available'
        self.number3.save()
        url = '/api/v2/numbers/%s' % self.number3.number
        data = {
            'state': 'released'
        }
        self.assertEqual(1, models.Number.objects.filter(
            pk=self.number3.pk).count())
        # Mock the NexmoProvider before sending the request.
        with mock.patch('endagaweb.views.api_v2.NexmoProvider') as mock_nexmo:
            response = self.client.post(url, data=data)
        self.assertEqual(200, response.status_code)
        # The mock NexmoProvider should've been called with specific args.
        self.assertTrue(mock_nexmo().cancel_number.called)
        args, _ = mock_nexmo().cancel_number.call_args
        self.assertEqual(self.number3.number, args[0])
        # The number should be deleted.
        self.assertEqual(0, models.Number.objects.filter(
            pk=self.number3.pk).count())


class TowerTest(TestCase):
    """Testing the BTS v2 API view."""

    @classmethod
    def setUpClass(cls):
        cls.user = models.User(username='g', email='g@l.com')
        cls.user.save()
        cls.user2 = models.User(username='h', email='m@h.com')
        cls.user2.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.user_profile2 = models.UserProfile.objects.get(user=cls.user2)
        uuid = "59216199-d664-4b7a-a2db-6f26e9a3d323"
        inbound_url = "http://localhost:8090"
        name = "test-tower-user-one"
        package_versions = {
            'endaga_version': '00000.00003.00020'
        }
        cls.bts = models.BTS(
            uuid=uuid, nickname=name, inbound_url=inbound_url, secret='ok',
            network=cls.user_profile.network,
            package_versions=json.dumps(package_versions))
        cls.bts.save()
        # Create an attached Subscriber and a UsageEvent.
        cls.sub = models.Subscriber(
            balance=100000, name='sub-one', imsi='IMSI999990000000555',
            network=cls.bts.network, bts=cls.bts)
        cls.sub.save()
        cls.event = models.UsageEvent(
            subscriber=cls.sub, bts=cls.bts, kind='local_sms', reason='test',
            date=datetime.datetime.now(pytz.utc))
        cls.event.save()

    @classmethod
    def tearDownClass(cls):
        """Destroy the objects we created for the test."""
        cls.user.delete()
        cls.user2.delete()
        cls.user_profile.delete()
        cls.user_profile2.delete()
        cls.bts.delete()
        cls.sub.delete()
        cls.event.delete()

    def setUp(self):
        self.client = Client()

    def test_get(self):
        """GET is not supported."""
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        url = '/api/v2/towers/%s' % self.bts.uuid
        response = self.client.get(url, **header)
        self.assertEqual(405, response.status_code)

    def test_post(self):
        """POST is not supported."""
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        data = {}
        url = '/api/v2/towers/%s' % self.bts.uuid
        response = self.client.post(url, data=data, **header)
        self.assertEqual(405, response.status_code)

    def test_delete_sans_token(self):
        """DELETE fails without a token."""
        url = '/api/v2/towers/%s' % self.bts.uuid
        header = {}
        response = self.client.delete(url, **header)
        self.assertEqual(403, response.status_code)

    def test_delete_wrong_token(self):
        """DELETE with the wrong token fails."""
        # Try to DELETE UserProfile1's BTS with UP2's API token.
        url = '/api/v2/towers/%s' % self.bts.uuid
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        response = self.client.delete(url, **header)
        self.assertEqual(403, response.status_code)

    def test_tower_version_too_low(self):
        """DELETEs should succeed even if the tower's software version is too
           low.
        """
        package_versions = {
            'endaga_version': '00000.00003.00019'
        }
        self.bts.package_versions = json.dumps(package_versions)
        self.bts.save()
        url = '/api/v2/towers/%s' % self.bts.uuid
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = self.client.delete(url, **header)
        self.assertEqual(200, response.status_code)

    def test_deregister(self):
        """We can deregister a tower via DELETE."""
        # Make sure the software version is setup correctly.
        package_versions = {
            'endaga_version': '00000.00003.00020'
        }
        self.bts.package_versions = json.dumps(package_versions)
        self.bts.save()
        # We should start with one tower and no deregistered towers.
        self.assertEqual(1, models.BTS.objects.count())
        self.assertEqual(0, models.DeregisteredBTS.objects.count())
        # Make the request.
        url = '/api/v2/towers/%s' % self.bts.uuid
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        response = self.client.delete(url, **header)
        self.assertEqual(200, response.status_code)
        # The BTS should have been deleted but the associated Sub and
        # UsageEvent should still exist.
        self.assertEqual(0, models.BTS.objects.count())
        self.assertEqual(1, models.Subscriber.objects.filter(
            pk=self.sub.pk).count())
        self.assertEqual(1, models.UsageEvent.objects.filter(
            kind='deregister_bts').count())
        # We should have one deregistered tower now and it should have the
        # original BTS's secret.
        dbts = models.DeregisteredBTS.objects.get(uuid=self.bts.uuid)
        self.assertEqual(self.bts.secret, dbts.secret)
        # Clean up the deregistered tower so this test doesn't affect any
        # others.
        models.DeregisteredBTS.objects.get(uuid=self.bts.uuid).delete()


class SubscriberTest(TestCase):
    """Testing the Subscriber API view."""

    @classmethod
    def setUpClass(cls):
        cls.user = models.User(username='g', email='g@l.com')
        cls.user.save()
        cls.user2 = models.User(username='u', email='u@m.com')
        cls.user2.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.user_profile2 = models.UserProfile.objects.get(user=cls.user2)
        # Create a BTS.
        uuid = "59216199-d664-4b7a-a2db-6f26e9a5d324"
        inbound_url = "http://localhost:8090"
        name = "test-tower-user-one"
        cls.bts = models.BTS(uuid=uuid, nickname=name, inbound_url=inbound_url,
                             secret='ok', network=cls.user_profile.network)
        cls.bts.save()
        # Create two subscribers, one for each tower, each with a number or
        # two.
        cls.imsi = "IMSI999990000000555"
        cls.sub = models.Subscriber(
            balance=100000, name='sub-one', imsi=cls.imsi,
            network=cls.bts.network, bts=cls.bts)
        cls.sub.save()
        cls.number = models.Number(number='6285574719324', state="inuse",
                                   network=cls.user_profile.network,
                                   subscriber=cls.sub,
                                   kind="number.nexmo.monthly")
        cls.number.save()
        cls.number2 = models.Number(number='6285574719443', state="inuse",
                                    network=cls.user_profile.network,
                                    subscriber=cls.sub,
                                    kind="number.nexmo.monthly")
        cls.number2.save()
        cls.imsi2 = "IMSI999990000000556"
        cls.sub2 = models.Subscriber(
            balance=100000, name='sub-two', imsi=cls.imsi2,
            network=cls.user_profile2.network, bts=None)
        cls.sub2.save()
        cls.number3 = models.Number(number='6285574719444', state="inuse",
                                    network=cls.user_profile2.network,
                                    subscriber=cls.sub2,
                                    kind="number.nexmo.monthly")
        cls.number3.save()
        cls.pcu = models.PendingCreditUpdate(subscriber=cls.sub, amount=100,
                                             uuid='abc123')
        cls.pcu.save()

    @classmethod
    def tearDownClass(cls):
        """Destroy the objects we created for the test."""
        cls.user.delete()
        cls.user2.delete()
        cls.user_profile.delete()
        cls.user_profile2.delete()
        cls.bts.delete()
        cls.sub.delete()
        cls.sub2.delete()
        cls.number.delete()
        cls.number2.delete()
        cls.number3.delete()
        cls.pcu.delete()

    def setUp(self):
        self.client = Client()

    def test_get(self):
        """GET is not supported."""
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        url = '/api/v2/subscribers/%s' % self.sub.imsi
        response = self.client.get(url, **header)
        self.assertEqual(405, response.status_code)

    def test_post(self):
        """POST is not supported."""
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        data = {}
        url = '/api/v2/subscribers/%s' % self.sub.imsi
        response = self.client.post(url, data=data, **header)
        self.assertEqual(405, response.status_code)

    def test_delete_sans_token(self):
        """DELETE fails without a token."""
        url = '/api/v2/subscribers/%s' % self.sub.imsi
        header = {}
        response = self.client.delete(url, **header)
        self.assertEqual(403, response.status_code)

    def test_delete_wrong_token(self):
        """DELETE with the wrong token fails."""
        # Try to DELETE UserProfile1's subscriber with UP2's API token.
        url = '/api/v2/subscribers/%s' % self.sub.imsi
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        response = self.client.delete(url, **header)
        self.assertEqual(403, response.status_code)

    def test_deactivate_subscriber(self):
        """We can deactivate the Subscriber via DELETE.

        Disassociates the subscriber with its BTS and Network.  Starts an async
        post task (which we will mock) to send this info to the client.
        Deactivates all numbers associated with the subscriber and creates a
        'delete_imsi' UsageEvent.  Also deletes all associated
        PendingCreditUpdates.
        """
        url = '/api/v2/subscribers/%s' % self.sub.imsi
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile.network.api_token
        }
        with mock.patch('endagaweb.celery.app.send_task') as mocked_task:
            response = self.client.delete(url, **header)
        self.assertEqual(200, response.status_code)
        # The subscriber should no longer be in the DB.
        self.assertEqual(0, models.Subscriber.objects.filter(
            imsi=self.sub.imsi).count())
        # Both of the associated numbers should have been deactivated -- reload
        # them from the DB to check their state.
        number = models.Number.objects.get(id=self.number.id)
        self.assertEqual('available', number.state)
        self.assertEqual(None, number.network)
        self.assertEqual(None, number.subscriber)
        number2 = models.Number.objects.get(id=self.number2.id)
        self.assertEqual('available', number2.state)
        # The associated PendingCreditUpdate should be gone.
        self.assertEqual(0, models.PendingCreditUpdate.objects.filter(
            pk=self.pcu.pk).count())
        # The mocked task should have been called with specific arguments
        self.assertTrue(mocked_task.called)
        args, _ = mocked_task.call_args
        task_name, task_args = args
        task_endpoint, task_data = task_args
        self.assertEqual('endagaweb.tasks.async_post', task_name)
        expected_url = '%s/config/deactivate_subscriber' % self.bts.inbound_url
        self.assertEqual(expected_url, task_endpoint)
        # The task_data should be signed with the BTS UUID and should have a
        # jwt key which is a dict with a imsi key.
        serializer = itsdangerous.JSONWebSignatureSerializer(self.bts.secret)
        task_data = serializer.loads(task_data['jwt'])
        self.assertEqual(self.sub.imsi, task_data['imsi'])
        # A 'delete_imsi' UsageEvent should have been created.
        event_count = models.UsageEvent.objects.filter(
            subscriber_imsi=self.sub.imsi, kind='delete_imsi').count()
        self.assertEqual(1, event_count)

    def test_deactivate_subscriber_sans_bts(self):
        """We can deactivate the Subscriber even if they are not camped.

        This is the case for self.sub2.
        """
        url = '/api/v2/subscribers/%s' % self.sub2.imsi
        header = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user_profile2.network.api_token
        }
        with mock.patch('endagaweb.tasks.async_post.delay') as mocked_task:
            response = self.client.delete(url, **header)
        self.assertEqual(200, response.status_code)
        # The subscriber should no longer be in the DB.
        self.assertEqual(0, models.Subscriber.objects.filter(
            imsi=self.sub2.imsi).count())
        # The associated number should have been deactivated -- reload it from
        # the DB to check its state.
        number3 = models.Number.objects.get(id=self.number3.id)
        self.assertEqual('available', number3.state)
        self.assertEqual(None, number3.network)
        self.assertEqual(None, number3.subscriber)
        # The mocked task should not have been called in this case because
        # there is no BTS to notify.
        self.assertFalse(mocked_task.called)
        # A 'delete_imsi' UsageEvent should have been created.
        event_count = models.UsageEvent.objects.filter(
            subscriber_imsi=self.sub2.imsi, kind='delete_imsi').count()
        self.assertEqual(1, event_count)
