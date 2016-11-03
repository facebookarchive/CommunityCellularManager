"""Staff-only views.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import json
import time
import urllib

from django import http
from django import template
from django.core import urlresolvers
from django.db.models.functions import Coalesce
from django.db.models import Q
from django.db.models import Sum
from django.db.models import Value
from django.shortcuts import redirect
from django.template.defaultfilters import slugify
import django_tables2 as tables
import pytz
from rest_framework import authentication
from rest_framework import permissions
from rest_framework import response
from rest_framework import status
from rest_framework import views as drf_views
from guardian.shortcuts import get_objects_for_user

from endagaweb import models
from endagaweb.forms.dashboard_forms import SelectNetworkForm
from endagaweb.forms.dashboard_forms import SelectTowerForm
from endagaweb.views import django_tables


class Numbers(drf_views.APIView):
    """View the list of Numbers."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request):
        """"Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        numbers = models.Number.objects.all()
        # Configure the table of numbers.  Do not show any pagination controls
        # if the total number of numbers is small.
        number_table = django_tables.NumberTable(list(numbers))
        numbers_per_page = 20
        paginate = False
        if numbers.count() > numbers_per_page:
            paginate = {'per_page': numbers_per_page}
        tables.RequestConfig(request, paginate=paginate).configure(
            number_table)
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'number_table': number_table,
        }
        # Render template.
        numbers_template = template.loader.get_template(
            'dashboard/staff/numbers.html')
        html = numbers_template.render(context, request)
        return http.HttpResponse(html)


class Towers(drf_views.APIView):
    """View the list of towers."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request):
        """"Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        # We create a convoluted queryset so that towers that have never synced
        # (last_active = None) sort after active and inactive towers.
        the_past = datetime.datetime.now() - datetime.timedelta(days=10*365)
        towers = models.BTS.objects.all().annotate(
            new_last_active=Coalesce('last_active', Value(the_past))).order_by(
                '-new_last_active')
        # Attach UserProfiles to each tower in the queryset.
        for tower in towers:
            tower_user_profiles = models.UserProfile.objects.filter(
                network=tower.network)
            for tower_user_profile in tower_user_profiles:
                if hasattr(tower, 'user_email'):
                    tower.user_email += ',' + tower_user_profile.user.email
                else:
                    tower.user_email = tower_user_profile.user.email
        # Configure the table of towers.
        tower_table = django_tables.StaffTowerTable(list(towers))
        towers_per_page = 8
        paginate = False
        if towers.count() > towers_per_page:
            paginate = {'per_page': towers_per_page}
        tables.RequestConfig(request, paginate=paginate).configure(
            tower_table)
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'towers': towers,
            'tower_table': tower_table,
        }
        # Render the template.
        towers_template = template.loader.get_template(
            'dashboard/staff/towers.html')
        html = towers_template.render(context, request)
        return http.HttpResponse(html)


class MarginAnalysis(drf_views.APIView):
    """Analyze Endaga and operator margins."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request):
        """"Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        # Build up the context and initial form data.
        initial_form_data = {}
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
        }
        network_pk = request.GET.get('network', None)
        if network_pk:
            initial_form_data['network'] = network_pk
            network = models.Network.objects.get(pk=network_pk)
            # Attach the associated UserProfile to the network for reference.
            network.user_profile = models.UserProfile.objects.get(
                network=network)
            context['network'] = network
            # Count subs and numbers.
            context['subscriber_count'] = models.Subscriber.objects.filter(
                network=network).count()
            context['number_count'] = models.Number.objects.filter(
                network=network).count()
            # Build up the data for the price comparison table.
            context['prices'] = []
            context['grand_total_op_profit'] = 0
            context['grand_total_e_profit'] = 0
            tiers = self.get_ordered_tiers(network)
            for traffic_type in ('call', 'sms'):
                for tier in tiers:
                    # Determine costs.  The URL params (keys) are of the form
                    # <call/sms>_<sluggified_tier_name>_proposed_<entity>_cost.
                    # We'll fill in the form with something that was POSTed or
                    # with a default value from the tier itself.
                    if traffic_type == 'call':
                        # Subscriber costs.
                        actual_sub_cost = tier.cost_to_subscriber_per_min
                        key = 'call_%s_proposed_%s_cost' % (
                            slugify(tier.name), 'sub')
                        proposed_sub_cost = int(request.GET.get(
                            key, actual_sub_cost))
                        # Operator costs.
                        actual_op_cost = tier.cost_to_operator_per_min
                        key = 'call_%s_proposed_%s_cost' % (
                            slugify(tier.name), 'op')
                        proposed_op_cost = int(request.GET.get(
                            key, actual_op_cost))
                        # Endaga costs.
                        actual_e_cost = self.get_cost(tier, 'call', 'e')
                        key = 'call_%s_proposed_%s_cost' % (
                            slugify(tier.name), 'e')
                        proposed_e_cost = int(request.GET.get(
                            key, actual_e_cost))
                    elif traffic_type == 'sms':
                        # Subscriber costs.
                        actual_sub_cost = tier.cost_to_subscriber_per_sms
                        key = 'sms_%s_proposed_%s_cost' % (
                            slugify(tier.name), 'sub')
                        proposed_sub_cost = int(request.GET.get(
                            key, actual_sub_cost))
                        # Operator costs.
                        actual_op_cost = tier.cost_to_operator_per_sms
                        key = 'sms_%s_proposed_%s_cost' % (
                            slugify(tier.name), 'op')
                        proposed_op_cost = int(request.GET.get(
                            key, actual_op_cost))
                        # Endaga costs.
                        actual_e_cost = self.get_cost(tier, 'sms', 'e')
                        key = 'sms_%s_proposed_%s_cost' % (
                            slugify(tier.name), 'e')
                        proposed_e_cost = int(request.GET.get(
                            key, actual_e_cost))
                    # Calculate margins.
                    op_margin = proposed_sub_cost - proposed_op_cost
                    e_margin = proposed_op_cost - proposed_e_cost
                    # Find the number of these kinds of events.
                    occurrences = self.count_usage_events(traffic_type, tier)
                    # Calculate profits in dollars.
                    total_op_profit = occurrences * op_margin / (1000 * 100.)
                    total_e_profit = occurrences * e_margin / (1000 * 100.)
                    context['grand_total_op_profit'] += total_op_profit
                    context['grand_total_e_profit'] += total_e_profit
                    # Now that we've done the math, format the values.
                    if traffic_type == 'call':
                        occurrences = '%0.2f' % occurrences
                    # Use all of this to set more of the context.
                    context['prices'].append({
                        'directionality': tier.directionality,
                        'tier': tier.name,
                        'traffic_type': traffic_type,
                        'proposed_sub_cost': proposed_sub_cost,
                        'actual_sub_cost': actual_sub_cost,
                        'proposed_op_cost': proposed_op_cost,
                        'actual_op_cost': actual_op_cost,
                        'proposed_e_cost': proposed_e_cost,
                        'actual_e_cost': actual_e_cost,
                        'op_margin': op_margin,
                        'e_margin': e_margin,
                        'occurrences': occurrences,
                        'total_op_profit': total_op_profit,
                        'total_e_profit': total_e_profit,
                    })
        # Attach the network selection form with any specified initial data.
        select_network_form = SelectNetworkForm(initial=initial_form_data)
        select_network_form.helper.form_action = (
            '/dashboard/staff/margin-analysis')
        context['select_network_form'] = select_network_form
        # Render the template.
        margin_template = template.loader.get_template(
            'dashboard/staff/margin-analysis.html')
        html = margin_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Handles POST requests.

        The forms on the analysis page POST here to set URL params.  This page
        then redirects to GET with those params set and the values are read out
        of the URL to determine how to run the actual computations.
        """
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        network = user_profile.network
        url_params = {}
        if request.POST.get('network', None):
            url_params['network'] = request.POST.get('network')
        # Encode the proposed prices from the table into the URL.  The 'name'
        # of each input is pretty convoluted and there are lots of inputs.
        # Each name and corresponding url param is a combo of the params below.
        traffic_types = ('call', 'sms')
        entities = ('sub', 'op', 'e')
        tiers = self.get_ordered_tiers(network)
        for entity in entities:
            for traffic_type in traffic_types:
                for tier in tiers:
                    key = '%s_%s_proposed_%s_cost' % (
                        traffic_type, slugify(tier.name), entity)
                    if request.POST.get(key, None):
                        # Only encode values in the URL when the proposed cost
                        # is different than the actual cost.
                        proposed = int(request.POST.get(key))
                        actual = self.get_cost(tier, traffic_type, entity)
                        if proposed != actual:
                            url_params[key] = proposed
        base_url = urlresolvers.reverse('margin-analysis')
        url = '%s?%s' % (base_url, urllib.urlencode(url_params))
        return redirect(url)

    def get_ordered_tiers(self, network):
        """Returns an ordered tuple of tiers for a network."""
        on_network_receive_tier = models.BillingTier.objects.get(
            network=network, directionality='on_network_receive')
        on_network_send_tier = models.BillingTier.objects.get(
            network=network, directionality='on_network_send')
        off_network_receive_tier = models.BillingTier.objects.get(
            network=network, directionality='off_network_receive')
        off_network_send_tier_a = models.BillingTier.objects.get(
            network=network, directionality='off_network_send',
            destination_group__name__contains='Tier A')
        off_network_send_tier_b = models.BillingTier.objects.get(
            network=network, directionality='off_network_send',
            destination_group__name__contains='Tier B')
        off_network_send_tier_c = models.BillingTier.objects.get(
            network=network, directionality='off_network_send',
            destination_group__name__contains='Tier C')
        off_network_send_tier_d = models.BillingTier.objects.get(
            network=network, directionality='off_network_send',
            destination_group__name__contains='Tier D')
        return (on_network_receive_tier, on_network_send_tier,
                off_network_receive_tier, off_network_send_tier_a,
                off_network_send_tier_b, off_network_send_tier_c,
                off_network_send_tier_d)

    def get_cost(self, tier, traffic_type, entity):
        """Determine the relevant cost from a BillingTier.

        If, for example, you pass in a tier, 'call', and 'op' this will return
        tier.cost_to_operator_per_min.
        """
        if traffic_type == 'sms' and entity == 'sub':
            return tier.cost_to_subscriber_per_sms
        elif traffic_type == 'sms' and entity == 'op':
            return tier.cost_to_operator_per_sms
        elif traffic_type == 'sms' and entity == 'e':
            # TODO!
            return 0
        if traffic_type == 'call' and entity == 'sub':
            return tier.cost_to_subscriber_per_min
        elif traffic_type == 'call' and entity == 'op':
            return tier.cost_to_operator_per_min
        elif traffic_type == 'call' and entity == 'e':
            # TODO!
            return 0

    def count_usage_events(self, traffic_type, tier):
        """Count UsageEvents of a specified type.

        For instance specifying 'sms' and 'on_network_receive' will return all
        UEs of type 'local_recv_sms'.  'call' type events will have their
        billsec summed rather than just the number of calls.
        """
        network = tier.network
        directionality = tier.directionality
        events = models.UsageEvent.objects
        filters = Q(network=network)
        # We will only gather events after Jul 30, 2014 due to an issue with
        # UsageEvent generation in Papua.
        JUL30_2014 = datetime.datetime(month=7, day=30, year=2014,
                                       tzinfo=pytz.utc)
        filters = filters & Q(date__gte=JUL30_2014)
        # SMS-types.
        if traffic_type == 'sms':
            mapping = {
                'on_network_receive': 'local_recv_sms',
                'on_network_send': 'local_sms',
                'off_network_receive': 'incoming_sms',
                'off_network_send': 'outside_sms',
            }
            filters = filters & Q(kind=mapping[directionality])
            # Off-network send events need further filtering by Tier.
            if directionality == 'off_network_send':
                filters = (filters & Q(
                    destination__destination_group=tier.destination_group))
            return events.filter(filters).count()
        # Call-types.
        elif traffic_type == 'call':
            mapping = {
                'on_network_receive': 'local_recv_call',
                'on_network_send': 'local_call',
                'off_network_receive': 'incoming_call',
                'off_network_send': 'outside_call',
            }
            filters = filters & Q(kind=mapping[directionality])
            # Off-network send events need further filtering by Tier.
            if directionality == 'off_network_send':
                filters = (filters & Q(
                    destination__destination_group=tier.destination_group))
            seconds = events.filter(filters).aggregate(
                Sum('billsec'))['billsec__sum']
            if seconds:
                return seconds / 60.
            else:
                return 0


class TowerMonitoring(drf_views.APIView):
    """Analyze and graph TimeseriesStats data for towers."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request):
        """"Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        # Build up the context and initial form data.
        initial_form_data = {}
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
        }
        tower_pk = request.GET.get('tower', None)
        if tower_pk:
            tower = models.BTS.objects.get(pk=tower_pk)
            context['tower'] = tower
            initial_form_data['tower'] = tower_pk
            # Check the version and whether there are any stats to display.
            context['endaga_version'] = json.loads(
                tower.package_versions)['endaga_version']
            context['tower_has_monitoring_stats'] = (
                models.TimeseriesStat.objects.filter(bts=tower).exists())
            # Inject the current time and the tz offset.
            context['current_time_epoch'] = int(time.time())
            context['timezone_offset'] = pytz.timezone(
                user_profile.timezone).utcoffset(
                    datetime.datetime.now()).total_seconds()
        context['select_tower_form'] = SelectTowerForm(
            initial=initial_form_data)
        # Render the template.
        timeseries_template = template.loader.get_template(
            'dashboard/staff/tower-monitoring.html')
        html = timeseries_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Handles POST requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        url_params = {}
        if request.POST.get('tower', None):
            url_params['tower'] = request.POST.get('tower')
        base_url = urlresolvers.reverse('tower-monitoring')
        url = '%s?%s' % (base_url, urllib.urlencode(url_params))
        return redirect(url)


class NetworkEarnings(drf_views.APIView):
    """Analyze network revenue and costs."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request):
        """"Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        # Build up the context and initial form data.
        initial_form_data = {}
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
        }
        network_pk = request.GET.get('network', None)
        if network_pk:
            # If a network has been selected, populate the form and the table.
            initial_form_data['network'] = network_pk
            network = models.Network.objects.get(pk=network_pk)
            context['network'] = network
            operator = models.UserProfile.objects.get(network=network)
            context['operator'] = operator
            # There were errors with the CC recharge system that occurred
            # multiple times before Feb 3, 2015.  So for analysis purposes,
            # we'll ignore data before that time.
            feb3_2015 = datetime.datetime(year=2015, month=2, day=3,
                                          tzinfo=pytz.utc)
            context['start_of_analysis'] = feb3_2015
            network_creation_date = operator.user.date_joined
            context['network_creation_date'] = network_creation_date
            if network_creation_date < feb3_2015:
                days_of_operation = (datetime.datetime.now(pytz.utc) -
                                     feb3_2015).days
            else:
                days_of_operation = (datetime.datetime.now(pytz.utc) -
                                     network_creation_date).days
            context['days_of_operation'] = days_of_operation
            # Calculate operator revenue (the sum of UsageEvent.change for
            # certain UsageEvent.kinds).  These change values are all negative
            # so we multiply by negative one to fix that.
            kinds = ['local_call', 'local_sms', 'outside_call', 'outside_sms',
                     'incoming_call', 'incoming_sms', 'local_recv_call',
                     'local_recv_sms']
            events = models.UsageEvent.objects.filter(
                network=network, kind__in=kinds, date__gte=feb3_2015).only(
                    'change')
            if events:
                credit = events.aggregate(Sum('change'))['change__sum']
                # Convert revenue to USD.
                conversion_to_usd = {
                    'USD': 1 / (100 * 1000.),
                    'IDR': 1 / 13789.50,
                }
                multiplier = conversion_to_usd[network.subscriber_currency]
                revenue = -1 * credit * multiplier
            else:
                revenue = 0
            context['revenue'] = revenue
            # Calculate operator costs (payments to Endaga).
            ledger = models.Ledger.objects.get(userp=operator)
            transactions = models.Transaction.objects.filter(
                ledger=ledger, kind='credit', reason='Automatic Recharge',
                created__gte=feb3_2015).only('amount')
            if transactions:
                costs = (transactions.aggregate(Sum('amount'))['amount__sum'] /
                         (100 * 1000.))
            else:
                costs = 0
            context['costs'] = costs
            # Determine the net profit.
            profit = revenue - costs
            context['profit'] = profit
            if days_of_operation != 0:
                context['profit_per_day'] = profit / float(days_of_operation)
            else:
                context['profit_per_day'] = None

        # Attach the network selection form with any specified initial data.
        select_network_form = SelectNetworkForm(initial=initial_form_data)
        select_network_form.helper.form_action = (
            '/dashboard/staff/network-earnings')
        context['select_network_form'] = select_network_form
        # Render the template.
        earnings_template = template.loader.get_template(
            'dashboard/staff/network-earnings.html')
        html = earnings_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Handles POST requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        if not user_profile.user.is_staff:
            return response.Response('', status=status.HTTP_404_NOT_FOUND)
        url_params = {}
        if request.POST.get('network', None):
            url_params['network'] = request.POST.get('network')
        base_url = urlresolvers.reverse('network-earnings')
        url = '%s?%s' % (base_url, urllib.urlencode(url_params))
        return redirect(url)
