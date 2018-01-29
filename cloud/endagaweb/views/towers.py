"""Tower views.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import json
import re
import time

from django import http
from django import template
import django_tables2 as tables
from django.utils.timesince import timesince
from django.contrib.gis.geos import Point
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import pytz
from rest_framework import authentication
from rest_framework import permissions
from rest_framework import views as drf_views
from guardian.shortcuts import get_objects_for_user

from endagaweb import models
from endagaweb.views.dashboard import ProtectedView
from endagaweb.views import django_tables


class TowerList(drf_views.APIView):
    """View the list of towers."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request):
        """"Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        towers = models.BTS.objects.filter(network=user_profile.network)
        # Configure the table of towers.  Do not show any pagination controls
        # if the total number of towers is small.
        tower_table = django_tables.TowerTable(list(towers))
        towers_per_page = 8
        paginate = False
        if len(towers) > towers_per_page:
            paginate = {'per_page': towers_per_page}
        tables.RequestConfig(request, paginate=paginate).configure(tower_table)
        # During tower creation, we'll suggest a simple tower nickname based
        # on the number of towers currenly on the network.  So if there are
        # already four towers on the network, we'll suggest a nickname of
        # 'Tower 5' for the next BTS.
        suggested_nickname = 'Tower %s' % (len(towers) + 1)
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'towers': towers,
            'tower_table': tower_table,
            'suggested_nickname': suggested_nickname,
        }
        # Render template.
        towers_template = template.loader.get_template('dashboard/towers.html')
        html = towers_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request):
        """Handles POST requests to add towers."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        uuid = request.POST.get('uuid')
        nickname = request.POST.get('nickname')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        response = {
            'status': 'ok',
            'messages': [],
        }
        # First validate -- make sure a UUID was submitted and is globally
        # unique.
        validation_failed = False
        if not validate_uuid(uuid):
            response['status'] = 'failed'
            response['messages'].append('Invalid UUID.')
            validation_failed = True
        elif models.BTS.objects.filter(uuid=uuid).count() > 0:
            response['status'] = 'failed'
            response['messages'].append('This tower is already registered.')
            validation_failed = True
        if latitude:
            try:
                latitude = float(latitude)
            except ValueError:
                response['status'] = 'failed'
                response['messages'].append('Invalid latitude.')
                validation_failed = True
        if longitude:
            try:
                longitude = float(longitude)
            except ValueError:
                response['status'] = 'failed'
                response['messages'].append('Invalid longitude.')
                validation_failed = True
        # Just return immediately if validation failed.
        if validation_failed:
            return http.HttpResponse(json.dumps(response),
                                     content_type="application/json")
        # Start building the BTS instance.
        tower = models.BTS(network=user_profile.network)
        tower.uuid = uuid
        if nickname:
            tower.nickname = nickname
        if latitude and longitude:
            tower.location = Point(longitude, latitude)
        # TODO(matt): ping the inbound URL.
        tower.save()
        return http.HttpResponse(json.dumps(response),
                                 content_type="application/json")


class TowerInfo(ProtectedView):
    """View info on a single tower."""

    def get(self, request, uuid=None):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        try:
            tower = models.BTS.objects.get(uuid=uuid,
                                           network=user_profile.network)
        except models.BTS.DoesNotExist:
            return http.HttpResponseBadRequest()
        # Humanize the uptime.
        uptime = None
        if tower.status == 'active' and tower.uptime:
            uptime = timesince(datetime.datetime.now() -
                               datetime.timedelta(seconds=tower.uptime))
        # Set the context with various stats.
        versions = json.loads(tower.package_versions)
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'tower': tower,
            'tower_endaga_version': tower.printable_version(
                versions['endaga_version']),
            'uptime': uptime,
        }
        # Render template.
        info_template = template.loader.get_template(
            'dashboard/tower_detail/info.html')
        html = info_template.render(context, request)
        return http.HttpResponse(html)


class TowerMonitor(ProtectedView):
    """View TimeseriesStats related to a single tower."""

    def get(self, request, uuid=None):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        try:
            tower = models.BTS.objects.get(
                uuid=uuid, network=user_profile.network)
        except models.BTS.DoesNotExist:
            return http.HttpResponseBadRequest()
        timezone_offset = pytz.timezone(user_profile.timezone).utcoffset(
            datetime.datetime.now()).total_seconds()
        # Check the version to see if the tower could have reported any stats.
        endaga_version = json.loads(tower.package_versions)['endaga_version']
        # See if the tower has any relevant stats to display.
        tower_has_monitoring_stats = models.TimeseriesStat.objects.filter(
            bts=tower).exists()
        # Build up the context.
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'tower': tower,
            'current_time_epoch': int(time.time()),
            'timezone_offset': timezone_offset,
            'endaga_version': endaga_version,
            'tower_has_monitoring_stats': tower_has_monitoring_stats,
        }
        # Render template.
        monitor_template = template.loader.get_template(
            'dashboard/tower_detail/monitor.html')
        html = monitor_template.render(context, request)
        return http.HttpResponse(html)


class TowerEdit(drf_views.APIView):
    """View and edit info for a single tower."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request, uuid=None):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        try:
            tower = models.BTS.objects.get(uuid=uuid,
                                           network=user_profile.network)
        except models.BTS.DoesNotExist:
            return http.HttpResponseBadRequest()
        # Set the response context.  If the tower nickname is None in the db,
        # pass an emtpy string into the initial form data so we don't populate
        # the input with 'None' (string).  Also set a suggesteed nickname for
        # the input placeholder text.
        current_number_of_towers = models.BTS.objects.filter(
            network=user_profile.network).count()
        suggested_nickname = 'Tower %s' % (current_number_of_towers + 1)
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'tower': tower,
            'tower_nickname': tower.nickname if tower.nickname else '',
            'suggested_nickname': suggested_nickname,
        }
        # Render template.
        edit_template = template.loader.get_template(
            'dashboard/tower_detail/edit.html')
        html = edit_template.render(context, request)
        return http.HttpResponse(html)

    def post(self, request, uuid=None):
        """Handles POST requests to edit towers."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        nickname = request.POST.get('nickname')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        response = {
            'status': 'ok',
            'messages': [],
        }
        # First validate -- make sure the UUID is globally unique and present.
        validation_failed = False
        try:
            tower = models.BTS.objects.get(uuid=uuid,
                                           network=user_profile.network)
        except models.BTS.DoesNotExist:
            response['messages'].append('Tower not found.')
            validation_failed = True
        if not uuid:
            response['messages'].append('Invalid UUID.')
            validation_failed = True
        if latitude:
            try:
                latitude = float(latitude)

            except ValueError:
                response['messages'].append('Invalid latitude.')
                validation_failed = True
        if longitude:
            try:
                longitude = float(longitude)
            except ValueError:
                response['messages'].append('Invalid longitude.')
                validation_failed = True
        # Return immediately if validation fails.
        if validation_failed:
            response['status'] = 'failed'
            return http.HttpResponse(json.dumps(response),
                                     content_type="application/json")
        if nickname:
            tower.nickname = nickname
        if latitude and longitude:
            tower.location = Point(longitude, latitude)
        tower.save()
        return http.HttpResponse(json.dumps(response),
                                 content_type="application/json")


class TowerDeregister(drf_views.APIView):
    """A UI for deregistering a single tower.

    The actual deregistration is done through the v2 API.
    """

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def get(self, request, uuid=None):
        """Handles GET requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)
        try:
            tower = models.BTS.objects.get(uuid=uuid,
                                           network=user_profile.network)
        except models.BTS.DoesNotExist:
            return http.HttpResponseBadRequest()
        endaga_version = json.loads(tower.package_versions)['endaga_version']
        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'tower': tower,
            'endaga_version': endaga_version,
            'status': tower.get_status_display(),
        }
        # Render template.
        edit_template = template.loader.get_template(
            'dashboard/tower_detail/deregister.html')
        html = edit_template.render(context, request)
        return http.HttpResponse(html)


class TowerEvents(drf_views.APIView):
    """View events for a single tower."""

    # Setup DRF permissions and auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
         authentication.TokenAuthentication)

    def get(self, request, *args, **kwargs):
        return self._handle_request(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._handle_request(request, *args, **kwargs)

    def _handle_request(self, request, uuid=None):
        """Handles GET and POST requests."""
        user_profile = models.UserProfile.objects.get(user=request.user)

        if request.method == "POST":
            page = 1
        elif request.method == "GET":
            page = request.GET.get('page', 1)
        else:
            return HttpResponseBadRequest()  # noqa: F821 T25377293 Grandfathered in

        try:
            tower = models.BTS.objects.get(uuid=uuid,
                              network=user_profile.network)
        except models.BTS.DoesNotExist:
            return http.HttpResponseBadRequest()
        endaga_version = json.loads(tower.package_versions)['endaga_version']
        events = models.SystemEvent.objects.filter(bts=tower).order_by('-date')

        # Paginate events
        event_paginator = Paginator(events, 25)
        try:
            events = event_paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            events = event_paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 999), deliver last page of results.
            events = event_paginator.page(event_paginator.num_pages)

        context = {
            'networks': get_objects_for_user(request.user, 'view_network', klass=models.Network),
            'user_profile': user_profile,
            'tower': tower,
            'endaga_version': endaga_version,
            'events': events,
        }
        # Render template.
        edit_template = template.loader.get_template(
            'dashboard/tower_detail/tower_events.html')
        html = edit_template.render(context, request)
        return http.HttpResponse(html)


def validate_uuid(value):
    """Checks that a submitted value is a string formatted like a UUID.

    Note this will match UUID4 only, via: stackoverflow.com/a/14166194/232638
    """
    if type(value) not in (str, unicode):
        return False
    value = value.lower()
    regex = ('^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-'
             r'[a-f0-9]{12}\Z')
    pattern = re.compile(regex)
    return bool(pattern.match(value))
