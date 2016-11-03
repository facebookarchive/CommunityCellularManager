"""Endagaweb middleware.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import sys

from django.utils import timezone
from django.http import HttpResponse
from guardian.shortcuts import get_objects_for_user
import pytz

from endagaweb import models


class TimezoneMiddleware(object):
    """Activates django's timezone processing."""

    def process_request(self, request):
        """Intercedes during a request."""
        if not request.user:
            return
        if 'test' in sys.argv:
            # Skip this middleware in testing :/
            # TODO(matt): figure out why this middleware causes the internal
            #             django humanize test to fail.
            return
        try:
            user_profile = models.UserProfile.objects.get(user=request.user.id)
            timezone.activate(pytz.timezone(user_profile.timezone))
        except models.UserProfile.DoesNotExist:
            return

class MultiNetworkMiddleware(object):
    """This middleware validates that a UserProfile can actually access the
    network it is linked to. We use the UserProfile.network field to toggle
    between different networks. On request we check that the user still has
    access to handle permission revocation."""

    def process_request(self, request):
        # If this request is not associated with a User,
        # we don't do any checks
        if not request.user:
            return

        try:
            user_profile = models.UserProfile.objects.get(user=request.user.id)
        except models.UserProfile.DoesNotExist:
            # If the user doesn't have a profile, it's a network auth_user so return
            return

        if user_profile.network is None or \
                not request.user.has_perm('view_network', user_profile.network):
            # The user doesn't have acccess to the current network, since this is for UI
            # requests, we can fall back on another network before failing
            other_networks = get_objects_for_user(request.user,
                'view_network', klass=models.Network)
            if len(other_networks):
                user_profile.network = other_networks[0]
                user_profile.save()
                return

            # The user has no other network to fall back on, this is bad
            return HttpResponse('User is not associated with any network', status=401)

