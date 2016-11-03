"""Testing subscriber detail views in endagaweb.views.dashboard.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from django import test
import mock

from endagaweb import models


class SubscriberBaseTest(test.TestCase):
    """Base tests for all subscriber detail pages."""

    @classmethod
    def setUpClass(cls):
        cls.user = models.User(username="abe", email="a@b.com")
        cls.password = 'test123'
        cls.user.set_password(cls.password)
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)

        cls.bts = models.BTS(
            uuid="12345abcd", nickname="testbts",
            inbound_url="http://localhost/test",
            network=cls.user_profile.network)
        cls.bts.save()

        cls.subscriber_imsi = 'IMSI000123'
        cls.subscriber_num = '5551234'
        cls.subscriber = models.Subscriber.objects.create(
            balance=100, name='test-name', imsi=cls.subscriber_imsi,
            network=cls.bts.network, bts=cls.bts)
        cls.subscriber.save()

        cls.number = models.Number(number=cls.subscriber_num, state="inuse",
                                   network=cls.user_profile.network,
                                   kind="number.nexmo.monthly",
                                   subscriber=cls.subscriber)
        cls.number.save()

        cls.adjust_credit_endpoint = (
            '/dashboard/subscribers/%s/adjust-credit' % cls.subscriber_imsi)
        # Drop all PCUs.
        for pcu in models.PendingCreditUpdate.objects.all():
            pcu.delete()

    @classmethod
    def tearDownClass(cls):
        """Deleting the objects created for the tests."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.subscriber.delete()
        cls.number.delete()

    def setUp(self):
        self.client = test.Client()
        self.client.login(username=self.user.username, password=self.password)


class SubscriberInfoTest(SubscriberBaseTest):
    """Testing endagaweb.views.dashboard.SubscriberInfo."""

    def test_get(self):
        response = self.client.get('/dashboard/subscribers/%s' %
                                   self.subscriber_imsi)
        self.assertEqual(200, response.status_code)


class SubscriberActivityTest(SubscriberBaseTest):
    """Testing endagaweb.views.dashboard.SubscriberActivity."""

    def test_get(self):
        response = self.client.get('/dashboard/subscribers/%s/activity' %
                                   self.subscriber_imsi)
        self.assertEqual(200, response.status_code)

    def test_get_with_query_params(self):
        query_params = ('services=call-other-sms-transfer'
                        '&end_date=2015-03-07-at-01.44PM'
                        '&start_date=2015-03-04-at-01.30PM'
                        '&keyword=asdf')
        base_url = '/dashboard/subscribers/%s/activity' % self.subscriber_imsi
        url = '%s?%s' % (base_url, query_params)
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)

    def test_post(self):
        """POSTing redirects us to GET."""
        data = (
            'keyword=test&'
            'start_date=2011-02-25 at 06:31AM&'
            'end_date=2011-02-28 at 07:02AM&'
            'services[]=call&'
            'services[]=sms&'
            'services[]=transfer&'
        )
        url = '/dashboard/subscribers/%s/activity' % self.subscriber_imsi
        response = self.client.post(
            url, data, content_type='application/x-www-form-urlencoded')
        # TODO(matt): check the format of the redirect URL
        self.assertEqual(302, response.status_code)


class SubscriberSendSMSTest(SubscriberBaseTest):
    """Testing endagaweb.views.dashboard.SubscriberSendSMS."""

    def test_get(self):
        response = self.client.get('/dashboard/subscribers/%s/send-sms' %
                                   self.subscriber_imsi)
        self.assertEqual(200, response.status_code)

    def test_post(self):
        """Sending an SMS should redirect and generate a new task."""
        data = {
            'message': 'test -- hi there',
        }
        url = '/dashboard/subscribers/%s/send-sms' % self.subscriber_imsi
        with mock.patch('endagaweb.tasks.async_post.delay') as mocked_task:
            self.client.post(url, data)
            self.assertTrue(mocked_task.called)
            args, _ = mocked_task.call_args
            task_endpoint, task_data = args
        expected_url = '%s/endaga_sms' % self.bts.inbound_url
        self.assertEqual(expected_url, task_endpoint)
        self.assertEqual('0000', task_data['sender'])
        self.assertEqual(self.number.number, task_data['to'])
        self.assertEqual(data['message'], task_data['text'])


class SubscriberAdjustCreditTest(SubscriberBaseTest):
    """Testing endagaweb.views.dashboard.SubscriberAdjustCredit."""

    def test_get(self):
        response = self.client.get(self.adjust_credit_endpoint)
        self.assertEqual(200, response.status_code)

    def test_post(self):
        """We can adjust credit like normal."""
        data = {
            'amount': 3000
        }
        with mock.patch('endagaweb.tasks.update_credit.delay') as mocked_task:
            self.client.post(self.adjust_credit_endpoint, data)
            # There should now be one PCU.
            self.assertEqual(1, models.PendingCreditUpdate.objects.count())
            self.assertTrue(mocked_task.called)
            args, _ = mocked_task.call_args
        task_imsi, task_msgid = args
        self.assertEqual(self.subscriber_imsi, task_imsi)
        pcu = models.PendingCreditUpdate.objects.all()[0]
        self.assertEqual(pcu.uuid, task_msgid)

    def test_post_large_value(self):
        """If the amount is too large, we fail and tell the user."""
        integer_field_max_size = 2147483647
        data = {
            'amount': integer_field_max_size + 1
        }
        response = self.client.post(self.adjust_credit_endpoint, data)
        self.assertEqual(302, response.status_code)
        # A PCU should not have been created.
        self.assertEqual(0, models.PendingCreditUpdate.objects.count())

    def test_post_non_number(self):
        """If the amount not a number, we fail and tell the user."""
        data = {
            'amount': 'five thousand'
        }
        response = self.client.post(self.adjust_credit_endpoint, data)
        self.assertEqual(302, response.status_code)
        # A PCU should not have been created.
        self.assertEqual(0, models.PendingCreditUpdate.objects.count())


class SubscriberEditTest(SubscriberBaseTest):
    """Testing endagaweb.views.dashboard.SubscriberEdit."""

    def test_get(self):
        response = self.client.get('/dashboard/subscribers/%s/edit' %
                                   self.subscriber_imsi)
        self.assertEqual(200, response.status_code)
