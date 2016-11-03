"""API V2 views.

/numbers/<number> -- POST to deactivate a number

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import json
import uuid

from django.conf import settings
import itsdangerous
import pytz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework import authentication
from rest_framework import permissions
from rest_framework.response import Response

from endagaweb.ic_providers.nexmo import NexmoProvider
from endagaweb.util.api import get_network_from_user
from endagaweb import models
from endagaweb import tasks

class Number(APIView):
    """Handles /api/v2/numbers and /api/v2/numbers/<number>."""

    # Setup DRF permissions and auth.  This endpoint should only be accessed
    # via token auth, but for DRF to work properly you must also enable
    # session auth.

    # CURRENTLY BROKEN FOR NON-NEXMO NUMBERS -Kurtis
    # https://github.com/endaga/endaga-web/issues/406
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def post(self, request, msisdn):
        network = get_network_from_user(request.user)
        number = models.Number.objects.get(number=msisdn)
        if (number.network and number.network != network
                and not request.user.is_staff):
            return Response("User is not associated with that Number %s %s." %(number.network.pk, network.pk),
                            status=status.HTTP_403_FORBIDDEN)
        # Must post a valid 'state'.
        valid_states = ('available', 'released')
        if request.POST.get('state', None) not in valid_states:
            return Response("Must post a valid state.",
                            status=status.HTTP_400_BAD_REQUEST)
        # This is a valid request, begin processing.  First check if this is a
        # number-deactivation request.
        if (number.state == 'inuse' and
                request.POST.get('state') == 'available'):
            # Refuse to deactivate a subscriber's last number.
            if (len(models.Number.objects.filter(subscriber=number.subscriber))
                    <= 1):
                message = ("Cannot deactivate a subscriber's last number."
                           "  Instead, delete the subscriber.")
                return Response(message, status=status.HTTP_400_BAD_REQUEST)
            # If it's not the subscriber's only number, send an async post to
            # the BTS to deactivate the number.  Sign the request using JWT.
            bts = number.subscriber.bts
            url = '%s/config/deactivate_number' % bts.inbound_url
            data = {
                'number': msisdn,
                # Add a UUID as a nonce for the message.
                'msgid': str(uuid.uuid4()),
            }
            serializer = itsdangerous.JSONWebSignatureSerializer(bts.secret)
            signed_data = {
                'jwt': serializer.dumps(data),
            }
            tasks.async_post.delay(url, signed_data)
            # Create a 'deactivate_number' UsageEvent.
            now = datetime.datetime.now(pytz.utc)
            reason = 'deactivated phone number: %s' % number.number
            event = models.UsageEvent.objects.create(
                subscriber=number.subscriber, date=now, bts=bts,
                kind='deactivate_number', to_number=number.number,
                reason=reason, oldamt=number.subscriber.balance,
                newamt=number.subscriber.balance, change=0)
            event.save()
            # Diassociate the Number from its former Subscriber and Network.
            number.subscriber = None
            number.network = None
            number.state = request.POST.get('state')
            number.save()
            return Response("")

        # Check if this is a number-release request.
        if request.POST.get('state') == 'released':
            # User must be staff to do this.
            if not request.user.is_staff:
                return Response("", status=status.HTTP_404_NOT_FOUND)
            # The number must not be 'inuse.'
            if number.state == 'inuse':
                return Response("", status=status.HTTP_400_BAD_REQUEST)
            # The number cannot be associated with a Sub.
            if number.subscriber:
                return Response("", status=status.HTTP_400_BAD_REQUEST)
            # Validation passes, release (cancel) the number.
            nexmo_provider = NexmoProvider(
                settings.ENDAGA['NEXMO_ACCT_SID'],
                settings.ENDAGA['NEXMO_AUTH_TOKEN'],
                settings.ENDAGA['NEXMO_INBOUND_SMS_URL'],
                None,
                settings.ENDAGA['NEXMO_INBOUND_VOICE_HOST'],
                country=number.country_id)
            if nexmo_provider.cancel_number(number.number):
                # Success, delete the number.
                number.delete()
                return Response("", status=status.HTTP_200_OK)
            else:
                print 'deleting number %s failed' % number.number
                return Response(
                    "", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Invalid request.
        return Response("", status=status.HTTP_400_BAD_REQUEST)


class Subscriber(APIView):
    """Handles /api/v2/subscribers and /api/v2/subscribers/<imsi>."""

    # Setup DRF permissions and auth.  This endpoint should only be accessed
    # via token auth, but for DRF to work properly you must also enable
    # session auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def delete(self, request, imsi):
        network = get_network_from_user(request.user)
        subscriber = models.Subscriber.objects.get(imsi=imsi)
        if subscriber.network != network:
            return Response("Network is not associated with that Subscriber.",
                            status=status.HTTP_403_FORBIDDEN)
        # This is a valid request, begin processing.
        subscriber.deactivate()
        return Response("")


class Tower(APIView):
    """Handles /api/v2/towers/<uuid>."""

    # Setup DRF permissions and auth.  This endpoint should only be accessed
    # via token auth, but for DRF to work properly you must also enable
    # session auth.
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (authentication.SessionAuthentication,
                              authentication.TokenAuthentication)

    def delete(self, request, tower_uuid):
        network = get_network_from_user(request.user)
        tower = models.BTS.objects.get(uuid=tower_uuid)
        if tower.network and tower.network != network:
            return Response("Network is not associated with that BTS.",
                            status=status.HTTP_403_FORBIDDEN)
        # Create a DerigisteredBTS instance.
        dbts = models.DeregisteredBTS(uuid=tower.uuid, secret=tower.secret)
        dbts.save()
        # Create a 'deregister_bts' UsageEvent.
        now = datetime.datetime.now(pytz.utc)
        if tower.nickname:
            name = 'tower "%s" (%s)' % (tower.nickname, tower.uuid)
        else:
            name = 'tower %s' % tower.uuid
        event = models.UsageEvent.objects.create(
            date=now, bts_uuid=tower.uuid, kind='deregister_bts',
            reason='deregistered %s' % name)
        event.save()
        # TODO(matt): generate revocation certs
        # And finally delete the BTS.
        tower.delete()
        return Response("")
