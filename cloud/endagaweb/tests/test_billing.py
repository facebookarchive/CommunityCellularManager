"""Tests for billing operators with stripe, setting up billing tiers and
calculating the cost of services for operators.

Usage:
  $ python manage.py test endagaweb.BillingTestCase
  $ python manage.py test endagaweb.BillingTierSetupTest

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

import json
import mock
import os
from random import randrange
import urllib

from django.core.exceptions import ObjectDoesNotExist
from django.test import Client
from django.test import TestCase
import stripe

from ccm.common.utils import xml_cdr
from endagaweb import models
from endagaweb import notifications
from endagaweb.billing import tier_setup
import endagaweb.views.api


def _set_network_credit(network, amount=-1):
    """ Add credit to a network, unless billing disabled. """
    if amount < 0:
        amount = randrange(1000, 1000000)
    if network.billing_enabled:
        network.add_credit(amount)
    else:
        amount = 0
    return amount


def _network_cost(network, cost):
    """ Check if billing is enabled, if not cost is effectively zero. """
    return cost if network.billing_enabled else 0


class OperatorBillingTest(TestCase):
    """Tests for operator billing and ledger effects.

    Our operator billing flow is as follows:

    * A set of new events come in from a box.
    * For each event, before an actual UsageEvent is generated, the type is
      parsed and the operator's account is billed based on the event type, the
      to / from numbers and the BillingTiers.
    * We use network.calculate_operator_cost to determine how much the event
      should cost per SMS or per minute of a call.
    * Then we user_profile.network.bill_for_sms or
      user_profile.network.bill_for_call which creates Transactions (unless
      billing is disabled for user_network)
    * Everytime a Transaction is created and saved, the operator's ledger's
      balance is updated and, if the new balance is below the recharge
      threshold, the operator's credit card is billed in a recharge / top-up.
    * If the recharge fails, things continue to work, but a staff member should
      be alerted.

    To ensure this happens atomically, we specially select the ledger object
    for transactional update when we adjust its balance, and save it. There's
    no way for the Ledger object in memory to "know" it needs to reload itself
    from the DB. Because of this, when you bill things, you have to manually
    reload the UserProfile to get the newest ledger balance from the DB in
    these tests. You'd have to do this in application code too, but since each
    request loads a new UserProfile we typically don't need to worry about it.
    """

    @classmethod
    def setUpClass(cls):
        """Setup a User and UserProfile."""
        cls.user = models.User(username="j", email="j@k.com")
        cls.user.set_password("test")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)

    @classmethod
    def tearDownClass(cls):
        """Clean up created objects."""
        cls.user.delete()
        cls.user_profile.delete()

    def refresh_user_profile(self):
        """Testing util method to reload the user_profile instance."""
        self.user_profile = models.UserProfile.objects.get(
            id=self.user_profile.id)

    def test_billing_enabled_global_setting(self):
        """Can disable billing globally by setting environment variable."""
        self.assertEqual(self.user_profile.network.billing_enabled,
                         os.environ.get("NW_BILLING", "True").lower() == "true")

    def test_balance_starts_at_zero(self):
        """Ledger balance starts at zero."""
        self.assertEqual(0, self.user_profile.network.ledger.balance)

    def test_network_add_credit(self):
        """We can add credit to a profile."""
        credit_amount = _set_network_credit(self.user_profile.network)
        self.refresh_user_profile()
        self.assertEqual(credit_amount,
                         self.user_profile.network.ledger.balance)

    def test_network_bill_for_number(self):
        """We can bill for numbers."""
        # Add some initial credit to the account.
        credit_amount = 80 * 100 * 1000
        credit_amount = _set_network_credit(self.user_profile.network,
                                            credit_amount)
        self.refresh_user_profile()
        self.assertEqual(credit_amount,
                         self.user_profile.network.ledger.balance)
        # Bill for a number and check that the balance has changed.  The cost
        # of a number is currently hardcoded to $1 USD / mo.
        self.user_profile.network.bill_for_number('5550987')
        self.refresh_user_profile()
        number_cost = _network_cost(self.user_profile.network,
                                    1 * 100 * 1000)
        self.assertEqual(credit_amount - number_cost,
                         self.user_profile.network.ledger.balance)

    def test_network_bill_for_sms(self):
        """We can bill for SMS."""
        # Add some initial credit to the account.
        credit_amount = _set_network_credit(self.user_profile.network)
        self.refresh_user_profile()
        # Bill for the SMS.
        cost_to_operator = 300
        self.user_profile.network.bill_for_sms(cost_to_operator, 'outside_sms')
        self.refresh_user_profile()
        cost_to_operator = _network_cost(self.user_profile.network,
                                         cost_to_operator)
        self.assertEqual(credit_amount - cost_to_operator,
                         self.user_profile.network.ledger.balance)

    def test_network_bill_for_call(self):
        """We can bill for calls."""
        # Add some initial credit to the account.
        credit_amount = _set_network_credit(self.user_profile.network)
        self.refresh_user_profile()
        # Bill for the call.
        cost_to_operator = 300
        billable_seconds = 30
        self.user_profile.network.bill_for_call(cost_to_operator,
                                                billable_seconds,
                                                'outside_call')
        self.refresh_user_profile()
        billable_minutes = billable_seconds / 60.
        cost_to_operator = _network_cost(self.user_profile.network,
                                         cost_to_operator)
        self.assertEqual(credit_amount - cost_to_operator * billable_minutes,
                         self.user_profile.network.ledger.balance)

    def test_call_billing_math(self):
        """We round correctly."""
        # Add some initial credit to the account.
        credit_amount = _set_network_credit(self.user_profile.network)
        self.refresh_user_profile()
        # Bill for the call.
        cost_to_operator = 100
        billable_seconds = 175
        self.user_profile.network.bill_for_call(cost_to_operator,
                                                billable_seconds,
                                                'incoming_call')
        self.refresh_user_profile()
        # We expect to round down to the nearest millicent.
        expected_cost = _network_cost(self.user_profile.network, 291)
        self.assertEqual(credit_amount - expected_cost,
                         self.user_profile.network.ledger.balance)

    def test_do_not_create_transaction_for_zero_second_call(self):
        """Zero second calls do not create Transactions."""
        original_number_of_transactions = models.Transaction.objects.count()
        # Attempt to bill for a zero second call => no Transaction created.
        self.user_profile.network.bill_for_call(100, 0, 'incoming_call')
        new_number_of_transactions = models.Transaction.objects.count()
        self.assertEqual(new_number_of_transactions,
                         original_number_of_transactions)


class RechargeTest(TestCase):
    """We can recharge an operator's account with the CC on file."""

    @classmethod
    def setUpClass(cls):
        # Mock the stripe package.  Explicitly define a mocked customers to
        # the dict conversion.  The mocked retrieved customer is somewhat
        # complex because UserProfile.network.delete_card calls dict() on it.
        cls.mock_stripe = mock.Mock()
        cls.mock_stripe.StripeError = stripe.StripeError
        models.stripe = cls.mock_stripe
        cls.mock_stripe.Customer = mock.Mock()
        retrieved_customer = mock.MagicMock()
        cls.mock_stripe.Customer.retrieve.return_value = retrieved_customer
        cls.mock_stripe.Charge = mock.Mock()
        # We will set this retrieved customer to be 'deleted' by default so the
        # delete_card method will return True.
        retrieved_customer.keys.return_value.__iter__.return_value = (
            ['deleted'])
        cls.mock_stripe.Customer.create.return_value = {
            "id": "zyx987",
            "cards": {
                "data": [{
                    "last4": "1234",
                    "brand": "Visa",
                    "exp_month": "01",
                    "exp_year": "2020"
                }]
            }
        }
        # Setup a User and UserProfile.
        cls.user = models.User(username="u", email="u@v.com")
        cls.user.set_password("test")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        card = {
            'number': '4242424242424242',
            'exp_month': 12,
            'exp_year': 2020,
            'cvc': 987
        }
        cls.user_profile.network.autoload_enable = True
        cls.user_profile.network.update_card(card)

    @classmethod
    def tearDownClass(cls):
        cls.user_profile.network.delete_card()
        cls.user_profile.delete()
        cls.user.delete()
        models.stripe = stripe

    def tearDown(self):
        """Clear any side effects and reset the Ledger's balance."""
        self.mock_stripe.Charge.create.side_effect = None
        self.user_profile.network.ledger.balance = 0
        self.refresh_user_profile()

    def refresh_user_profile(self):
        """Testing util method to reload the user_profile instance."""
        self.user_profile = models.UserProfile.objects.get(
            id=self.user_profile.id)
        self.user_profile.network = models.Network.objects.get(
            id=self.user_profile.network.id)

    def test_recharge(self):
        """We should be able to recharge a user's account."""
        # Mock the Stripe charges and perform the recharge; it should succeed
        # (if billing enabled for the network).
        self.mock_stripe.Charge.create.return_value = mock.Mock()
        self.assertEqual(self.user_profile.network.recharge_if_necessary(),
                         self.user_profile.network.billing_enabled)
        # Initial ledger balance is zero; after recharge ledger balance
        # should equal network recharge amount.
        self.refresh_user_profile()
        new_balance = _network_cost(
            self.user_profile.network,
            self.user_profile.network.recharge_amount)
        self.assertEqual(new_balance,
                         self.user_profile.network.ledger.balance)

    def test_recharge_zero_amount(self):
        """If the recharge amount is set to zero, we should not recharge."""
        self.user_profile.network.recharge_amount = 0
        self.assertFalse(self.user_profile.network.recharge_if_necessary())

    def test_no_card(self):
        """Recharges should fail if the user has no associated card."""
        self.user_profile.network.delete_card()
        self.assertEqual(self.user_profile.network.stripe_cust_token, "")
        self.mock_stripe.Customer.retrieve.side_effect = stripe.StripeError
        self.assertFalse(self.user_profile.network.recharge_if_necessary())
        # Repair the side effect.
        self.mock_stripe.Customer.retrieve.side_effect = None

    def test_failed_recharge_triggers_staff_alert(self):
        pass

    def test_automatic_recharge(self):
        """A recharge is attempted if the balance falls below a threshold."""
        # Add some initial credit to the account.
        self.refresh_user_profile()
        credit_amount = _set_network_credit(
            self.user_profile.network,
            self.user_profile.network.recharge_thresh + 1000)
        self.refresh_user_profile()
        # Send an SMS.
        sms_cost = 3000
        self.user_profile.network.bill_for_sms(sms_cost, 'outside_sms')
        self.refresh_user_profile()
        # That should take us below the recharge threshold and charge the card
        # (unless network billing disabled).
        self.assertEqual(self.mock_stripe.Charge.create.called,
                         self.user_profile.network.billing_enabled)
        self.refresh_user_profile()
        delta = _network_cost(self.user_profile.network,
                              (sms_cost -
                               self.user_profile.network.recharge_amount))
        expected_credit = credit_amount - delta
        self.assertEqual(expected_credit,
                         self.user_profile.network.ledger.balance)


class CalculateOperatorCostTest(TestCase):
    """We can calculate cost to operators for SMS and calls."""

    @classmethod
    def setUpClass(cls):
        # Setup a Network by way of User -> UserProfile post-create hooks.
        cls.user = models.User(username="m", email="m@t.com")
        cls.user.set_password("test")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.network = cls.user_profile.network
        cls.bts = models.BTS(uuid="ddgghh3322", nickname="test-bts",
                             inbound_url="http://localhost/test",
                             network=cls.user_profile.network)
        cls.bts.save()
        # Mock the network.get_lowest_tower_version method so that it returns a
        # version where BillingTiers are supported.  Without this, the lowest
        # tower version will be None and all prices will default to Tier A.
        cls.original_version_lookup = cls.network.get_lowest_tower_version
        cls.network.get_lowest_tower_version = lambda: '0.1'

    @classmethod
    def tearDownClass(cls):
        """Cleanup the objects created for the test."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.network.delete()

    def test_local_receive_sms(self):
        """Local receive SMS should cost the default."""
        cost = self.network.calculate_operator_cost('on_network_receive',
                                                    'sms')
        self.assertEqual(0, cost)

    def test_local_send_sms(self):
        """Local send SMS should cost the default."""
        cost = self.network.calculate_operator_cost('on_network_send', 'sms')
        self.assertEqual(0, cost)

    def test_local_receive_call(self):
        """Local receive calls should cost the default."""
        cost = self.network.calculate_operator_cost('on_network_receive',
                                                    'call')
        self.assertEqual(0, cost)

    def test_local_send_call(self):
        """Local sent calls should cost the default."""
        cost = self.network.calculate_operator_cost('on_network_send', 'call')
        self.assertEqual(0, cost)

    def test_off_network_received_sms(self):
        """Off-network received SMS should cost the default."""
        cost = self.network.calculate_operator_cost('off_network_receive',
                                                    'sms')
        self.assertEqual(500, cost)

    def test_off_network_received_call(self):
        """Off-network received calls should cost the default."""
        cost = self.network.calculate_operator_cost('off_network_receive',
                                                    'call')
        self.assertEqual(2000, cost)

    def test_outbound_call_to_the_united_states(self):
        """The US and Canada (prefix 1) should be in Tier A by default."""
        destination_number = ''.join(['1', '1235554567'])
        cost = self.network.calculate_operator_cost(
            'off_network_send', 'call', destination_number)
        self.assertEqual(5000, cost)

    def test_outbound_call_to_jamaica(self):
        """Jamaica (prefix 1876) should be in Tier C by default.

        This one's a bit tricky because the prefix match could see the leading
        '1' and think it's US and Canada.
        """
        destination_number = ''.join(['1876', '1235554567'])
        cost = self.network.calculate_operator_cost(
            'off_network_send', 'call', destination_number)
        self.assertEqual(27000, cost)

    def test_outbound_call_to_angola(self):
        """Angola (prefix 244) should be in Tier B by default."""
        destination_number = ''.join(['244', '1235554567'])
        cost = self.network.calculate_operator_cost(
            'off_network_send', 'call', destination_number)
        self.assertEqual(13000, cost)

    def test_outbound_call_with_plus(self):
        """Numbers that include a '+' symbol should still work.

        This is a US/Canada number which should be Tier A by default.
        """
        destination_number = ''.join(['+1', '1235554567'])
        cost = self.network.calculate_operator_cost(
            'off_network_send', 'call', destination_number)
        self.assertEqual(5000, cost)

    def test_get_outbound_sms_cost_when_billing_tier_has_changed(self):
        """We can get the altered cost to an operator.

        Greenland (prefix 299) should be in Tier D by default.  We will adjust
        the operator cost in Tier D and see if that is reflected when we try to
        get the cost via the network method.
        """
        new_cost_to_operator_per_sms = 8888
        greenland = models.Destination.objects.get(prefix='299')
        tier_d = models.BillingTier.objects.get(
            network=self.network,
            destination_group=greenland.destination_group)
        tier_d.cost_to_operator_per_sms = new_cost_to_operator_per_sms
        tier_d.save()
        destination_number = ''.join(['299', '1235554567'])
        cost = self.network.calculate_operator_cost(
            'off_network_send', 'sms', destination_number)
        self.assertEqual(new_cost_to_operator_per_sms, cost)

    def test_old_towers(self):
        """Old towers that don't support Billing Tiers default to Tier A."""
        # Restore the mocked cost lookup to the original.
        self.network.get_lowest_tower_version = self.original_version_lookup
        # Force the endaga metapackage to have an 'undefined' version (the case
        # for old towers.)
        versions = {
            'endaga_version': None,
            'freeswitch_version': None,
            'gsm_version': None,
            'python_endaga_core_version': None,
            'python_gsm_version': None,
        }
        self.bts.package_versions = json.dumps(versions)
        self.bts.save()
        # This is Angola again, ordinarily Tier B.
        destination_number = ''.join(['244', '1235554567'])
        cost = self.network.calculate_operator_cost(
            'off_network_send', 'call', destination_number)
        self.assertEqual(5000, cost)
        # Repair the mock for the sake of other tests.
        self.network.get_lowest_tower_version = lambda: '0.1'


class BillingTierSetupTest(TestCase):
    """Tests for endagaweb.billing.tier_setup.

    These tests will just generate the Tier data once and then make assertions
    on the results.
    """

    @classmethod
    def setUpClass(cls):
        cls.data = tier_setup.create_tier_data()
        cls.off_send_tiers = [t for t in cls.data if
                              t['directionality'] == 'off_network_send']
        cls.off_receive_tiers = [t for t in cls.data if
                                 t['directionality'] == 'off_network_receive']
        cls.on_send_tiers = [t for t in cls.data if
                             t['directionality'] == 'on_network_send']
        cls.on_receive_tiers = [t for t in cls.data if
                                t['directionality'] == 'on_network_receive']
        for tier in cls.off_send_tiers:
            if tier['name'] == 'Off-Network Sending, Tier A':
                cls.tier_a = tier
            if tier['name'] == 'Off-Network Sending, Tier B':
                cls.tier_b = tier
            if tier['name'] == 'Off-Network Sending, Tier C':
                cls.tier_c = tier
            if tier['name'] == 'Off-Network Sending, Tier D':
                cls.tier_d = tier

    @classmethod
    def tearDownClass(cls):
        # Django 1.8 seems to require a tearDownClass whereever there is a
        # setUpClass (or use super).  See stackoverflow.com/questions/29653129
        pass

    def test_number_of_tiers_created(self):
        """Expect seven tiers to be created."""
        self.assertEqual(7, len(self.data))

    def test_directionality_of_tiers(self):
        """Expect seven specific tiers to be created."""
        self.assertEqual(4, len(self.off_send_tiers))
        self.assertEqual(1, len(self.off_receive_tiers))
        self.assertEqual(1, len(self.on_send_tiers))
        self.assertEqual(1, len(self.on_receive_tiers))

    def test_total_number_of_destinations(self):
        """Expect 217 total destinations.

        This is the number of unique prefixes in the Nexmo billing spreadsheet.
        There are actually 212 in the Outbound SMS sheet and an additional 5 in
        Outbound Voice, but we expect the parser to return the larger number.
        """
        destination_count = 0
        for tier in self.off_send_tiers:
            destination_count += len(tier['destinations'])
        self.assertEqual(217, destination_count)

    def test_destinations_in_only_one_tier(self):
        """Each destination should appear in only one tier."""
        all_destinations = []
        for tier in self.off_send_tiers:
            all_destinations.extend(tier['destinations'])
        for destination in all_destinations:
            tiers_containing_destination = 0
            for tier in self.off_send_tiers:
                if destination in tier['destinations']:
                    tiers_containing_destination += 1
            self.assertEqual(1, tiers_containing_destination)

    def test_united_states_and_canada_in_tier_a(self):
        """The US and Canada share prefix 1 so their country names should be
        combined.
        """
        countries = [d['country_name'] for d in self.tier_a['destinations']]
        self.assertTrue('US and Canada' in countries)

    def test_hong_kong_in_tier_b(self):
        countries = [d['country_name'] for d in self.tier_b['destinations']]
        self.assertTrue('Hong Kong' in countries)

    def test_russia_and_kazakhstan_in_tier_c(self):
        """Kazakhstan and Russia share prefix 7 so their country names should
        be combined.
        """
        countries = [d['country_name'] for d in self.tier_c['destinations']]
        self.assertTrue('Russia and Kazakhstan' in countries)

    def test_israel_in_tier_c(self):
        """There are multiple voice and SMS prices for Israel (prefix 972).  We
        should take the higher of the two when it comes to tier-creation.

        This test unfortunately might not test that capability, depending on
        the price breaks.  We are currently testing the 'production' billing
        tier definition file -- it would be nice to also have some test yaml
        files to test edge cases.
        """
        countries = [d['country_name'] for d in self.tier_c['destinations']]
        self.assertTrue('Israel' in countries)

    def test_uganda_in_tier_c(self):
        countries = [d['country_name'] for d in self.tier_c['destinations']]
        self.assertTrue('Uganda' in countries)

    def test_switzerland_in_tier_d(self):
        countries = [d['country_name'] for d in self.tier_d['destinations']]
        self.assertTrue('Switzerland' in countries)

    def test_subscriber_costs_match_operator_costs(self):
        """Sub prices should match operator costs initially."""
        operator_sms_cost = self.tier_a['cost_to_operator_per_sms']
        subscriber_sms_cost = self.tier_a['cost_to_subscriber_per_sms']
        self.assertEqual(operator_sms_cost, subscriber_sms_cost)
        operator_voice_cost = self.tier_a['cost_to_operator_per_min']
        subscriber_voice_cost = self.tier_a['cost_to_subscriber_per_min']
        self.assertEqual(operator_voice_cost, subscriber_voice_cost)


class SMSAPIBillingTest(TestCase):
    """Tests for endagaweb.views.api.SendNexmoSMS and InboundNexmoSMS.

    We should bill the operator for inbound and outbound SMS in these API
    handlers.
    """

    @classmethod
    def setUpClass(cls):
        # Setup a UserProfile, BTS, Subscriber and Number.
        cls.user = models.User(username="dal", email="d@l.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        # Add some initial credit to the user profile and disable CC recharge.
        cls.credit_amount = _set_network_credit(cls.user_profile.network,
                                                10 * 1e5)
        cls.user_profile.network.autoload_enable = False
        cls.user_profile.save()

        # mock out notifications' celery
        cls.old_celery_app = notifications.celery_app
        notifications.celery_app = mock.MagicMock()

        cls.bts = models.BTS(uuid="332244abc", nickname="testbts",
                             inbound_url="http://localhost/test",
                             network=cls.user_profile.network)
        cls.bts.save()
        # Mark the BTS active so that it's not in a no-data state and thus,
        # when we try to get the network's lowest tower version, this BTS will
        # be considered.  This lowest version matters when activating certain
        # billing features.
        cls.bts.mark_active()
        cls.subscriber_number = '19195550987'
        cls.subscriber = models.Subscriber.objects.create(
            balance=2*1e5, name='test-subscriber', imsi='IMSI000123000',
            network=cls.bts.network, bts=cls.bts)
        cls.subscriber.save()
        cls.number = models.Number(number=cls.subscriber_number, state="inuse",
                                   network=cls.user_profile.network,
                                   kind="number.nexmo.monthly",
                                   subscriber=cls.subscriber)
        cls.number.save()
        # Mock the Providers used by the outbound handler.
        cls.original_providers = endagaweb.views.api.SendSMS.HANDLERS
        #this is a really ugly hack to make mocks work here
        endagaweb.views.api.SendSMS.HANDLERS = { "number.nexmo.monthly" : (mock.Mock(),
                                                                           "id",
                                                                           "pw",
                                                                           "ib_sms",
                                                                           "ob_sms",
                                                                           "ib_voice")
                                            }
        # Mock the tasks used by the inbound handler.
        cls.original_tasks = endagaweb.views.api.tasks
        endagaweb.views.api.tasks = mock.Mock()
        # Setup the api client, SMS endpoints and the token-based auth.
        cls.client = Client()
        cls.send_endpoint = '/api/v1/send/'
        cls.inbound_endpoint = '/api/v1/inbound/'
        cls.header = {
            'HTTP_AUTHORIZATION': 'Token %s' % cls.user_profile.network.api_token
        }

    @classmethod
    def tearDownClass(cls):
        # Repair the mocked Provider and tasks.
        endagaweb.views.api.SendSMS.HANDLERS = cls.original_providers
        endagaweb.views.api.tasks = cls.original_tasks
        notifications.celery_app = cls.old_celery_app
        # Destroy objects created in the tests.
        cls.user.delete()
        cls.user_profile.delete()
        cls.bts.delete()
        cls.subscriber.delete()
        cls.number.delete()

    def refresh_user_profile(self):
        """Testing util method to reload the user_profile instance."""
        self.user_profile = models.UserProfile.objects.get(
            id=self.user_profile.id)

    def test_send_sms_to_tier_a(self):
        """We should bill the operator when SMS are sent to Tier A numbers."""
        data = {
            'from': '19195550987',
            # Laos (prefix 856) is in Tier A.
            'to': ''.join(['856', '9195557890']),
            'body': 'hi there',
        }
        self.client.post(self.send_endpoint, data, **self.header)
        self.refresh_user_profile()
        tier_a_sms_cost = _network_cost(self.user_profile.network, 2000)
        self.assertEqual(self.credit_amount - tier_a_sms_cost,
                         self.user_profile.network.ledger.balance)

    def test_send_sms_to_tier_b(self):
        """We should bill the operator when SMS are sent to Tier B numbers."""
        # Force the endaga metapackage to have a valid, non-None version so
        # that we correcly bill for this as Tier B.  Old towers with the
        # default version (None) will bill everything outbound as Tier A.
        v1 = self.bts.sortable_version('1.0.0')
        versions = {
            'endaga_version': v1,
            'freeswitch_version': v1,
            'gsm_version': v1,
            'python_endaga_core_version': v1,
            'python_gsm_version': v1,
        }
        self.bts.package_versions = json.dumps(versions)
        self.bts.save()
        data = {
            'from': '19195550987',
            # Zambia (prefix 260) is in Tier B.
            'to': ''.join(['260', '9195557890']),
            'body': 'hi there',
        }
        self.client.post(self.send_endpoint, data, **self.header)
        self.refresh_user_profile()
        tier_b_sms_cost = _network_cost(self.user_profile.network, 5000)
        self.assertEqual(self.credit_amount - tier_b_sms_cost,
                         self.user_profile.network.ledger.balance)

    def test_receive_sms(self):
        """We should bill the operator when we receive SMS from Nexmo."""
        # Tweak the inbound tier's operator cost to make this more interesting.
        off_receive_tier = models.BillingTier.objects.get(
            network=self.user_profile.network,
            directionality='off_network_receive')
        off_receive_tier.cost_to_operator_per_sms = 2000
        off_receive_tier.save()
        data = {
            'msisdn': ''.join(['260', '9195557890']),
            'to': self.subscriber_number,
            'text': 'hi there',
        }
        self.client.post(self.inbound_endpoint, data, **self.header)
        self.refresh_user_profile()
        expected_cost = _network_cost(
            self.user_profile.network,
            off_receive_tier.cost_to_operator_per_sms)
        expected_balance = self.credit_amount - expected_cost
        self.assertEqual(expected_balance,
                         self.user_profile.network.ledger.balance)


class VoiceBillingTest(TestCase):
    """Testing the BillVoice API view."""

    # Setup some CDR files.
    basepath = './endagaweb/tests/fixtures'
    with open("%s/cloud_to_bts.cdr.xml" % basepath) as cdrfile:
        incoming_xml = cdrfile.read()
        incoming_xc = xml_cdr.CloudVoiceCdr.from_xml(incoming_xml)
    with open("%s/bts_to_cloud.cdr.xml" % basepath) as cdrfile:
        outgoing_xml = cdrfile.read()
        outgoing_xc = xml_cdr.CloudVoiceCdr.from_xml(outgoing_xml)
    with open("%s/bts_to_bts.cdr.xml" % basepath) as cdrfile:
        internal_xml = cdrfile.read()
        internal_xc = xml_cdr.CloudVoiceCdr.from_xml(internal_xml)
    with open("%s/invalid.cdr.xml" % basepath) as cdrfile:
        invalid_xml = cdrfile.read()

    @classmethod
    def setUpClass(cls):
        cls.user = models.User(username='v', email='v@v.com')
        cls.user.save()
        cls.user2 = models.User(username='w', email='w@w.com')
        cls.user2.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.user_profile2 = models.UserProfile.objects.get(user=cls.user2)
        # Give the users some credit so they don't try to recharge.
        fifty_bucks = endagaweb.util.currency.dollars2mc(50)
        cls.initial_credit = _set_network_credit(cls.user_profile.network,
                                                 fifty_bucks)
        cls.initial_credit2 = _set_network_credit(cls.user_profile2.network,
                                                  fifty_bucks)
        # Refresh the objects so the ledger balances reload.
        cls.user_profile = models.UserProfile.objects.get(
            id=cls.user_profile.id)
        cls.user_profile2 = models.UserProfile.objects.get(
            id=cls.user_profile2.id)
        # Create a BTS for each user profile.
        uuid = "59216199-d664-4b7a-a2db-6f26e9a5e203"
        inbound_url = "http://localhost:8090"
        name = "user1_testtower"
        cls.bts = models.BTS(uuid=uuid, nickname=name, inbound_url=inbound_url,
                             network=cls.user_profile.network)
        cls.bts.save()
        uuid = "1eac9487-fc7c-4674-8c38-dab66d6125c4"
        inbound_url = "http://localhost:8090"
        name = "user2_testtower"
        cls.bts2 = models.BTS(
            uuid=uuid, nickname=name, inbound_url=inbound_url,
            network=cls.user_profile2.network)
        cls.bts2.save()
        # Create two numbers to test intra-network calls.
        cls.imsi = "IMSI999990000000000"
        cls.num = 6285574719464
        cls.number = models.Number(
            number=cls.num, state="available",
            network=cls.user_profile.network, kind="number.nexmo.monthly")
        cls.number.save()
        cls.imsi2 = "IMSI999990000000001"
        cls.num2 = 6285574719465
        cls.number2 = models.Number(
            number=cls.num2, state="available",
            network=cls.user_profile2.network, kind="number.nexmo.monthly")
        cls.number2.save()

    @classmethod
    def tearDownClass(cls):
        """Destroy the objects we created for the test."""
        cls.user.delete()
        cls.user2.delete()
        cls.user_profile.delete()
        cls.user_profile2.delete()
        cls.bts.delete()
        cls.bts2.delete()
        cls.number.delete()
        cls.number2.delete()

    def test_outgoing_voice_cdr(self):
        """We can process outgoing voice CDRs."""
        client = Client()
        response = client.post(
            "/internal/api/v1/voice/",
            data='cdr=%s' % (urllib.quote_plus(self.outgoing_xml), ),
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(200, response.status_code)
        # Refresh the user profile to get the latest balance.
        self.user_profile = models.UserProfile.objects.get(user=self.user)
        # The destination number's prefix is 62 (Indonesia),
        # which is in Tier A.
        duration = self.outgoing_xc["billsec"]
        expected_cost = _network_cost(
            self.user_profile.network,
            int((duration / 60.) * 5000))
        self.assertEqual(self.initial_credit - expected_cost,
                         self.user_profile.network.ledger.balance)

    def test_incoming_voice_cdr(self):
        """We can process incoming voice CDRs."""
        # Tweak the off_network_receive tier's operator cost to make this more
        # interesting than the default (zero cost).
        off_receive_tier = models.BillingTier.objects.get(
            network=self.user_profile.network,
            directionality='off_network_receive')
        off_receive_tier.cost_to_operator_per_min = 300
        off_receive_tier.save()
        client = Client()
        response = client.post(
            "/internal/api/v1/voice/",
            data='cdr=%s' % (urllib.quote_plus(self.incoming_xml), ),
            content_type='application/x-www-form-urlencoded')
        # Refresh the user profile to get the latest balance.
        self.user_profile = models.UserProfile.objects.get(user=self.user)
        # Get billable duration of CDR
        duration = self.incoming_xc["billsec"]
        expected_cost = _network_cost(
            self.user_profile.network,
            int((duration / 60.) * off_receive_tier.cost_to_operator_per_min))
        transaction_list = models.Transaction.objects.order_by('created')
        search_args = {"kind": "incoming_call",
                       "ledger": self.user_profile.network.ledger}
        if self.user_profile.network.billing_enabled:
            transaction = transaction_list.get(**search_args)
            self.assertEqual(-1 * transaction.amount, expected_cost)
        else:
            with self.assertRaises(ObjectDoesNotExist):
                transaction = transaction_list.get(**search_args)
        self.assertEqual(self.initial_credit - expected_cost,
                         self.user_profile.network.ledger.balance)

    def test_internal_voice_cdr(self):
        """We can process internal call CDRs.

        These are actually a very interesting edge case where the caller and
        destination are both using Endaga sims, but they are on different
        networks (owned by different operators).  We actually bill for this as
        any other incoming / outside call but really we are short-circuiting
        Nexmo in this case.
        """
        # Tweak the off_network_receive tier's operator cost to make this more
        # interesting than the default (zero cost).
        off_receive_tier = models.BillingTier.objects.get(
            network=self.user_profile.network,
            directionality='off_network_receive')
        off_receive_tier.cost_to_operator_per_min = 300
        off_receive_tier.save()
        client = Client()
        response = client.post(
            "/internal/api/v1/voice/",
            data='cdr=%s' % (urllib.quote_plus(self.internal_xml), ),
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(200, response.status_code)
        # Refresh the user profiles to get the latest balance.
        self.user_profile = models.UserProfile.objects.get(user=self.user)
        self.user_profile2 = models.UserProfile.objects.get(user=self.user2)
        # The destination number's prefix is 62 (Indonesia),
        # which is in Tier A.
        duration = self.internal_xc["billsec"]
        expected_incoming_cost = _network_cost(self.user_profile2.network,
                                               int((duration / 60.) * 2000))
        expected_outside_cost = _network_cost(self.user_profile.network,
                                              int((duration / 60.) * 5000))
        # User Profile 1 is the caller and 2 is the recipient.
        self.assertEqual(self.initial_credit2 - expected_incoming_cost,
                         self.user_profile2.network.ledger.balance)
        self.assertEqual(self.initial_credit - expected_outside_cost,
                         self.user_profile.network.ledger.balance)

    def test_invalid_voice_cdr(self):
        """We can process invalid CDRs."""
        client = Client()
        response = client.post(
            "/internal/api/v1/voice/",
            data='cdr=%s' % (urllib.quote_plus(self.invalid_xml), ),
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(404, response.status_code)

    def test_bad_xml_voice_cdr(self):
        """We can handle bad XML."""
        client = Client()
        response = client.post(
                "/internal/api/v1/voice/",
                data='cdr=%s' % urllib.quote_plus("<mhm>"),
                content_type='application/x-www-form-urlencoded')
        self.assertEqual(400, response.status_code)

    def test_missing_xml_voice_cdr(self):
        """We can handle even more bad XML!"""
        client = Client()
        response = client.post(
                "/internal/api/v1/voice/",
                data='cdr=%s' % urllib.quote_plus("<yup/>"),
                content_type='application/x-www-form-urlencoded')
        self.assertEqual(400, response.status_code)
