"""Network views.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import time
import json

from django import http
from django import template
from django.contrib import messages
from django.core import urlresolvers
from django.db import transaction
from django.shortcuts import redirect
import django_tables2 as tables
from guardian.shortcuts import get_objects_for_user
from django.conf import settings

from ccm.common.currency import parse_credits, humanize_credits, \
    CURRENCIES, DEFAULT_CURRENCY
from endagaweb import models
from endagaweb.forms import dashboard_forms
from endagaweb.views.dashboard import ProtectedView
from endagaweb.views import django_tables


NUMBER_COUNTRIES = {
    'US': 'United States (+1)',
    'CA': 'Canada (+1)',
    'SE': 'Sweden (+46)',
    'ID': 'Indonesia (+62)',
    'PH': 'Philippines (+63)',
}


class NetworkInfo(ProtectedView):
    """View info on a single network."""

    def get(self, request):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network

        # Determine the current version and latest client releases.  We need to
        # use the printable_version function and for that we need a BTS
        # instance (which will just reside in memory and not be saved).
        bts = models.BTS()
        current_version = bts.printable_version(
            network.get_lowest_tower_version())

        latest_stable_version = None
        tmp_objs = models.ClientRelease.objects.filter(channel='stable').order_by('-date')
        if (tmp_objs):
            latest_stable_version = tmp_objs[0].version

        latest_beta_version = None
        tmp_objs = models.ClientRelease.objects.filter(channel='beta').order_by('-date')
        if (tmp_objs):
            latest_beta_version = tmp_objs[0].version

        # Count the associated numbers, towers and subscribers.
        towers_on_network = models.BTS.objects.filter(network=network).count()
        subscribers_on_network = models.Subscriber.objects.filter(
            network=network).count()
        numbers_on_network = models.Number.objects.filter(
            network=network).count()
        # Count the 30-, 7- and 1-day active subs.
        thirty_days = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        seven_days = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        one_day = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        thirty_day_actives = models.Subscriber.objects.filter(
            last_active__gt=thirty_days, network=network).count()
        seven_day_actives = models.Subscriber.objects.filter(
            last_active__gt=seven_days, network=network).count()
        one_day_actives = models.Subscriber.objects.filter(
            last_active__gt=one_day, network=network).count()
        # Count the camped subscribers.  Unfortunately the Django ORM cannot
        # filter on properties.
        all_subs = models.Subscriber.objects.filter(network=network)
        camped_right_now = len([s for s in all_subs if s.is_camped])
        # Set the context with various stats.
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'currency': CURRENCIES[user_profile.network.subscriber_currency],
            'user_profile': user_profile,
            'network': network,
            'number_country': NUMBER_COUNTRIES[network.number_country],
            'current_version': current_version,
            'latest_stable_version': latest_stable_version,
            'latest_beta_version': latest_beta_version,
            'towers_on_network': towers_on_network,
            'subscribers_on_network': subscribers_on_network,
            'numbers_on_network': numbers_on_network,
            'thirty_day_actives': thirty_day_actives,
            'seven_day_actives': seven_day_actives,
            'one_day_actives': one_day_actives,
            'camped_right_now': camped_right_now,
        }
        # Render template.
        info_template = template.loader.get_template(
            'dashboard/network_detail/info.html')
        html = info_template.render(context, request)
        return http.HttpResponse(html)


class NetworkInactiveSubscribers(ProtectedView):
    """Edit settings for expiring inactive subs."""

    def get(self, request):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        # Find subscribers that, with the current settings, will soon be
        # deactivated.  Also divide that group up into "protected" and
        # "unprotected" subs.
        inactive_subs = network.get_outbound_inactive_subscribers(
            network.sub_vacuum_inactive_days)
        protected_subs = []
        unprotected_subs = []
        for sub in inactive_subs:
            if sub.prevent_automatic_deactivation:
                protected_subs.append(sub)
            else:
                unprotected_subs.append(sub)
        # Setup tables showing both groups of subs.
        protected_subs_table = django_tables.MinimalSubscriberTable(
            protected_subs)
        unprotected_subs_table = django_tables.MinimalSubscriberTable(
            unprotected_subs)
        tables.RequestConfig(request, paginate={'per_page': 25}).configure(
            protected_subs_table)
        tables.RequestConfig(request, paginate={'per_page': 25}).configure(
            unprotected_subs_table)
        # Set the context with various stats.
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'network': network,
            'sub_vacuum_form': dashboard_forms.SubVacuumForm({
                'sub_vacuum_enabled': network.sub_vacuum_enabled,
                'inactive_days': network.sub_vacuum_inactive_days,
            }),
            'protected_subs': protected_subs,
            'unprotected_subs': unprotected_subs,
            'protected_subs_table': protected_subs_table,
            'unprotected_subs_table': unprotected_subs_table,
        }
        # Render template.
        vacuum_template = template.loader.get_template(
            'dashboard/network_detail/inactive-subscribers.html')
        html = vacuum_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Handles post requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        with transaction.atomic():
            if 'sub_vacuum_enabled' in request.POST:
                enabled = 'True' == request.POST['sub_vacuum_enabled']
                network.sub_vacuum_enabled = enabled
                network.save()
            if 'inactive_days' in request.POST:
                try:
                    inactive_days = int(request.POST['inactive_days'])
                    if inactive_days > 10000:
                        inactive_days = 10000
                    network.sub_vacuum_inactive_days = inactive_days
                    network.save()
                except ValueError:
                    text = 'The "inactive days" parameter must be an integer.'
                    messages.error(request, text,
                                   extra_tags="alert alert-danger")
            messages.success(
                request, 'Subscriber auto-deletion settings saved.',
                extra_tags='alert alert-success')
        return redirect(urlresolvers.reverse('network-inactive-subscribers'))


class NetworkPrices(ProtectedView):
    """View pricing for a single network."""

    def get(self, request):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        # We will show a very different UI for networks that have old towers --
        # only one off-network send tier will be displayed and other text will
        # change.
        network_version = network.get_lowest_tower_version()
        # Start building context for the template.
        tiers = models.BillingTier.objects.filter(network=network)
        billing_tiers = []
        for tier in tiers:
            # Setup sensible labels for the traffic_enabled checkbox.
            if tier.directionality == 'off_network_send':
                label = ('Allow subscribers to make calls and send SMS to'
                         ' numbers not in this network.')
                note = ('The costs when a subscriber sends an SMS or makes a'
                        ' call to one of the countries below.')
            elif tier.directionality == 'off_network_receive':
                label = ('Allow subscribers to receive calls and SMS from'
                         ' numbers not in this network.')
                note = ('The costs when a subscriber receives an SMS or a call'
                        ' from a number outside of your network.')
            elif tier.directionality == 'on_network_send':
                label = ('Allow subscribers to make calls and send SMS to'
                         ' numbers that are in this network.')
                note = ('The costs when a subscriber on your network makes a'
                        ' call or sends an SMS to a number also on your'
                        ' network.')
            elif tier.directionality == 'on_network_receive':
                label = ('Allow subscribers to receive calls and SMS from'
                         ' numbers that are in this network.')
                note = ('The costs when a subscriber on your network receives'
                        ' a call or SMS from a subscriber who is also on your'
                        ' network.')
            # Get a list of countries for each off_network_send tier.
            destinations = models.Destination.objects.filter(
                destination_group=tier.destination_group)
            countries = [d.country_name for d in destinations]
            countries.sort()
            countries = ', '.join(countries)
            tier_data = {
                'name': tier.name,
                'directionality': tier.directionality,
                'id': tier.id,
                'cost_to_subscriber_per_min': tier.cost_to_subscriber_per_min,
                'cost_to_subscriber_per_sms': tier.cost_to_subscriber_per_sms,
                'cost_to_operator_per_min': tier.cost_to_operator_per_min,
                'cost_to_operator_per_sms': tier.cost_to_operator_per_sms,
                'countries_in_tier': countries,
                'traffic_enabled_label': label,
                'note': note,
            }
            billing_tiers.append(tier_data)
        # Sort the tiers so they show up in a sensible order on the dashboard.
        # Note that if the version is None, we dont' show the Off-Network
        # Sending Tiers B, C and D.
        if network_version == None:
            billing_tiers_sorted = 4 * [None]
        else:
            billing_tiers_sorted = 7 * [None]
        for tier in billing_tiers:
            if tier['name'] == 'On-Network Receiving Tier':
                billing_tiers_sorted[0] = tier
            elif tier['name'] == 'On-Network Sending Tier':
                billing_tiers_sorted[1] = tier
            elif tier['name'] == 'Off-Network Receiving Tier':
                billing_tiers_sorted[2] = tier
            elif tier['name'] == 'Off-Network Sending, Tier A':
                billing_tiers_sorted[3] = tier
            if network_version == None:
                continue
            if tier['name'] == 'Off-Network Sending, Tier B':
                billing_tiers_sorted[4] = tier
            elif tier['name'] == 'Off-Network Sending, Tier C':
                billing_tiers_sorted[5] = tier
            elif tier['name'] == 'Off-Network Sending, Tier D':
                billing_tiers_sorted[6] = tier
        # Build up some dynamic example data for use in the help text.
        country_name = 'Iceland'
        destination = models.Destination.objects.get(country_name=country_name)
        billing_tier = models.BillingTier.objects.get(
            destination_group=destination.destination_group, network=network)
        # Create the context for the template.
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'currency': CURRENCIES[user_profile.network.subscriber_currency],
            'user_profile': user_profile,
            'network': network,
            'billing_tiers': billing_tiers_sorted,
            'example': {
                'country_name': country_name,
                'billing_tier_name': billing_tier.name,
                'cost_to_subscriber_per_min': (
                    billing_tier.cost_to_subscriber_per_min),
                'cost_to_operator_per_min': (
                    billing_tier.cost_to_operator_per_min),
            },
            'network_version': network_version,
        }
        # Render template.
        prices_template = template.loader.get_template(
            'dashboard/network_detail/prices.html')
        html = prices_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Handles POSTs -- changes to the billing tiers."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        if 'tier_id' not in request.POST:
            return http.HttpResponseBadRequest()
        # Make sure the Tier exists and the correct UserProfile is associated
        # with it.
        try:
            billing_tier = models.BillingTier.objects.get(
                id=request.POST['tier_id'], network=network)
        except models.BillingTier.DoesNotExist:
            return http.HttpResponseBadRequest()
        # Redirect to GET, appending the billing-tier-section-{id} anchor so
        # the page hops directly to the billing tier that was just edited.
        billing_redirect = redirect('%s#billing-tier-section-%s' % (
            urlresolvers.reverse('network-prices'), billing_tier.id))
        error_text = 'Error: cost is negative or too large'
        try:
            currency = CURRENCIES[user_profile.network.subscriber_currency]
            cost_to_subscriber_per_min = self.parse_subscriber_cost(
                request.POST['cost_to_subscriber_per_min'], currency)
            cost_to_subscriber_per_sms = self.parse_subscriber_cost(
                request.POST['cost_to_subscriber_per_sms'], currency)
        except ValueError:
            messages.error(request, error_text)
            return billing_redirect
        billing_tier.cost_to_subscriber_per_min = \
            cost_to_subscriber_per_min.amount_raw
        billing_tier.cost_to_subscriber_per_sms = \
            cost_to_subscriber_per_sms.amount_raw
        if request.POST.get('traffic_enabled'):
            billing_tier.traffic_enabled = True
        else:
            billing_tier.traffic_enabled = False
        billing_tier.save()
        return billing_redirect

    def parse_subscriber_cost(self, string, currency=DEFAULT_CURRENCY):
        """Parses input cost strings for the network prices page and performs
        value checks. Outputs a Money instance. The cost must be non-negative
        and the integer reperesentation must fit in a 32 bit signed integer.

        Arguments:
            string: numerical string with support for thousands commas and
            decimal places
            currency: the desired output currency. Default currency
            controlled by common/currency extension
        Returns:
            A Money instance
        Raises:
            ValueError: if the string doesn't parse or is out of bounds.
        """
        money = parse_credits(string, currency)
        if money.amount_raw < 0:
            raise ValueError("Cost must be non-negative")
        # This is the max value that is allowed by the DB
        if money.amount_raw > 2147483647:
            raise ValueError("Value is too large")
        return money


class NetworkEdit(ProtectedView):
    """Edit basic network info (but not prices)."""

    def get(self, request):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        # Set the context with various stats.
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'network': network,
            'network_settings_form': dashboard_forms.NetworkSettingsForm({
                'network_name': network.name,
                'subscriber_currency': network.subscriber_currency,
                'number_country': network.number_country,
                'autoupgrade_enabled': network.autoupgrade_enabled,
                'autoupgrade_channel': network.autoupgrade_channel,
                'autoupgrade_in_window': network.autoupgrade_in_window,
                'autoupgrade_window_start': network.autoupgrade_window_start,
            }),
        }
        # Render template.
        edit_template = template.loader.get_template(
            'dashboard/network_detail/edit.html')
        html = edit_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Handles post requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        with transaction.atomic():
            if 'network_name' in request.POST:
                network.name = str(request.POST['network_name'])
                network.save()
            if 'subscriber_currency' in request.POST:
                network.subscriber_currency = str(
                    request.POST['subscriber_currency'])
                network.save()
            if 'number_country' in request.POST:
                if request.POST['number_country'] not in NUMBER_COUNTRIES:
                    return http.HttpResponseBadRequest()
                network.number_country = request.POST['number_country']
                network.save()
            if 'autoupgrade_enabled' in request.POST:
                # Convert to boolean.
                enabled = 'True' == request.POST['autoupgrade_enabled']
                network.autoupgrade_enabled = enabled
                network.save()
            if 'autoupgrade_channel' in request.POST:
                # Validate the POSTed channel, defaulting to stable.
                valid_channels = [
                    v[0] for v in models.ClientRelease.channel_choices]
                if request.POST['autoupgrade_channel'] not in valid_channels:
                    network.autoupgrade_channel = 'stable'
                else:
                    network.autoupgrade_channel = (
                        request.POST['autoupgrade_channel'])
                network.save()
            if 'autoupgrade_in_window' in request.POST:
                # Convert to boolean.
                in_window = 'True' == request.POST['autoupgrade_in_window']
                network.autoupgrade_in_window = in_window
                network.save()
        # Validate the autoupgrade window format outside of the transaction so,
        # if this fails, the rest of the options will still be saved.
        if 'autoupgrade_window_start' in request.POST:
            window_start = request.POST['autoupgrade_window_start']
            try:
                time.strptime(window_start, '%H:%M:%S')
                network.autoupgrade_window_start = window_start
                network.save()
            except ValueError:
                messages.error(request, "Invalid start time format.",
                               extra_tags="alert alert-danger")
                return redirect(urlresolvers.reverse('network-edit'))
        # All values were saved successfully, redirect back to editing.
        messages.success(request, "Network information updated.",
                         extra_tags="alert alert-success")
        return redirect(urlresolvers.reverse('network-edit'))

class NetworkSelectView(ProtectedView):
    """This is a view that allows users to switch their current
    network. They must have view_network permission on the instance
    for this to work.
    """

    def get(self, request, network_id):
        user_profile = models.UserProfile.objects.get(user=request.user)
        try:
            network = models.Network.objects.get(pk=network_id)
        except models.Network.DoesNotExist:
            return http.HttpResponseBadRequest()

        if not request.user.has_perm('view_network', network):
            return http.HttpResponse('User not permitted to view this network', status=401)

        user_profile.network = network
        user_profile.save()
        return http.HttpResponseRedirect(request.META.get('HTTP_REFERER', '/dashboard'))


class NetworkDenomination(ProtectedView):
    """Assign denominations bracket for recharge/adjust-credit in network."""

    def get(self, request):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        currency = network.subscriber_currency

        # Count the associated denomination with selected network.
        denom = models.NetworkDenomination.objects.filter(network=network)
        denom_count = denom.count()

        dnm_id = request.GET.get('id', None)
        if dnm_id:
            response = {
                'status': 'ok',
                'messages': [],
                'data': {}
            }
            denom = models.NetworkDenomination.objects.get(id=dnm_id)
            denom_data = {
                'id': denom.id,
                'start_amount': humanize_credits(denom.start_amount,
                                                 CURRENCIES[currency]).amount,
                'end_amount': humanize_credits(denom.end_amount,
                                               CURRENCIES[currency]).amount,
                'validity_days': denom.validity_days
            }
            response["data"] = denom_data
            return http.HttpResponse(json.dumps(response),
                                     content_type="application/json")

        # Configure the table of denominations. Do not show any pagination
        # controls if the total number of donominations is small.
        if not user_profile.user.is_staff:
            denom_table = django_tables.DenominationListTable(list(denom))
        else:
            denom_table = django_tables.DenominationTable(list(denom))
        towers_per_page = 8
        paginate = False
        if denom > towers_per_page:
            paginate = {'per_page': towers_per_page}
        tables.RequestConfig(request, paginate=paginate).configure(denom_table)

        # Set the context with various stats.
        context = {
            'networks': get_objects_for_user(request.user, 'view_network',
                                             klass=models.Network),
            'currency': CURRENCIES[user_profile.network.subscriber_currency],
            'user_profile': user_profile,
            'network': network,
            'number_country': NUMBER_COUNTRIES[network.number_country],
            'denomination': denom_count,
            'denominations_table': denom_table,
        }
        # Render template.
        info_template = template.loader.get_template(
            'dashboard/network_detail/denomination.html')
        html = info_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Operators can use this API to add denomination to a network.

        These denomination bracket will be used to recharge subscriber,
        set balance validity and status
        """
        user_profile = models.UserProfile.objects.get(user=request.user)
        network = user_profile.network
        try:
            currency = network.subscriber_currency
            start_amount_raw = request.POST.get('start_amount')
            start_amount = parse_credits(start_amount_raw,
                                         CURRENCIES[currency]).amount_raw
            end_amount_raw = request.POST.get('end_amount')
            end_amount = parse_credits(end_amount_raw,
                                       CURRENCIES[currency]).amount_raw
            validity_days = int(request.POST.get('validity_days')) or 0

            dnm_id = int(request.POST.get('dnm_id')) or 0
            if validity_days > settings.ENDAGA['MAX_VALIDITY_DAYS']:
                message = ('Validity days value exceeds maximum permissible '
                           'limit (%s Days).' %
                           (settings.ENDAGA['MAX_VALIDITY_DAYS']))
                messages.error(
                    request, message,
                    extra_tags='alert alert-danger')
                return redirect(urlresolvers.reverse('network-denominations'))
            elif start_amount <= 0 or end_amount <= 0:
                messages.error(request,
                               'Enter value >0 for start/end amount.',
                               extra_tags='alert alert-danger')
                return redirect(urlresolvers.reverse('network-denominations'))
            elif validity_days <= 0:
                messages.error(
                    request, 'Validity can not be 0 day.',
                    extra_tags='alert alert-danger')
                return redirect(urlresolvers.reverse('network-denominations'))
            elif end_amount <= start_amount:
                messages.error(
                    request, 'End amount should be greater than start amount.',
                    extra_tags='alert alert-danger')
                return redirect(urlresolvers.reverse('network-denominations'))

            user_profile = models.UserProfile.objects.get(user=request.user)
            with transaction.atomic():
                if dnm_id > 0:
                    try:
                        denom = models.NetworkDenomination.objects.get(
                            id=dnm_id)
                        # Check for existing denomination range exist.
                        denom_exists = \
                          models.NetworkDenomination.objects.filter(
                              end_amount__gte=start_amount,
                              start_amount__lte=end_amount,
                              network=user_profile.network).exclude(
                                  id=dnm_id).count()
                        if denom_exists:
                            messages.error(
                                request, 'Denomination range already exists.',
                                extra_tags='alert alert-danger')
                            return redirect(
                                urlresolvers.reverse('network-denominations'))
                        denom.network = user_profile.network
                        denom.start_amount = start_amount
                        denom.end_amount = end_amount
                        denom.validity_days = validity_days
                        denom.save()
                        messages.success(
                            request, 'Denomination is updated successfully.',
                            extra_tags='alert alert-success')
                    except models.NetworkDenomination.DoesNotExist:
                        messages.error(
                            request, 'Invalid denomination ID.',
                            extra_tags='alert alert-danger')
                        return redirect(
                            urlresolvers.reverse('network-denominations'))
                else:
                    # Check for existing denomination range exist.
                    denom_exists = models.NetworkDenomination.objects.filter(
                        end_amount__gte=start_amount,
                        start_amount__lte=end_amount,
                        network=user_profile.network).count()
                    if denom_exists:
                        messages.error(
                            request, 'Denomination range already exists.',
                            extra_tags='alert alert-danger')
                        return redirect(
                            urlresolvers.reverse('network-denominations'))
                    # Create new denomination for selected network
                    denom = models.NetworkDenomination(
                        network=user_profile.network)
                    denom.network = user_profile.network
                    denom.start_amount = start_amount
                    denom.end_amount = end_amount
                    denom.validity_days = validity_days
                    denom.save()
                    messages.success(
                        request, 'Denomination is created successfully.',
                        extra_tags='alert alert-success')
        except Exception:
            messages.error(request,
                           'Invalid validity value. Enter greater than '
                           '0 digit value',
                           extra_tags='alert alert-danger')
        return redirect(urlresolvers.reverse('network-denominations'))

    def delete(self, request):
        """Handles delete requests."""
        response = {
            'status': 'ok',
            'messages': [],
        }
        dnm_id = request.GET.get('id') or False
        if dnm_id:
            try:
                denom = models.NetworkDenomination.objects.get(id=dnm_id)
                denom.delete()
                response['status'] = 'success'
                messages.success(request, 'Denomination deleted successfully.',
                                 extra_tags='alert alert-success')
            except models.NetworkDenomination.DoesNotExist:
                response['status'] = 'failed'
                messages.error(
                    request, 'Invalid denomination ID.',
                    extra_tags='alert alert-danger')
        else:
            response['status'] = 'failed'
            messages.error(
                request, 'Invalid request data.',
                extra_tags='alert alert-danger')
        return http.HttpResponse(json.dumps(response),
                                 content_type="application/json")
