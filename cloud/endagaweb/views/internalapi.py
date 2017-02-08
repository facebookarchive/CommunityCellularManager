""" CCM internal API views.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import urlparse
import xml.dom.minidom
import xml.parsers.expat

from rest_framework import status
from rest_framework.authentication import (BaseAuthentication,
                                           TokenAuthentication,
                                           SessionAuthentication)
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from ccm.common import logger
from endagaweb.util.api import get_network_from_user
from endagaweb.models import Number, BTS, UserProfile, Network

class NumberLookup(APIView):
    """Given a number, gives the IP and port of the BTS it is currently
    registered to, across all users.

    Security issues: this function allow determining whether a number is in
    use.  Access should be restricted to internal requests only.
    """
    def get(self, request):
        if "number" not in request.GET:
            return Response("No number specified.",
                            status=status.HTTP_400_BAD_REQUEST)
        query_num = request.GET["number"]
        try:
            n = Number.objects.get(number=query_num)
            if n.state == 'inuse':
                if not n.subscriber:
                    # See issue 260.
                    print 'Error: number %s has no subscriber' % n.number
                    return Response(
                        'Number %s has no associated subscriber.' % n.number,
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                if not n.subscriber.bts:
                    # See issue 386.
                    print 'Error: subscriber "%s" has no BTS' % n.subscriber
                    return Response(
                        'Subscriber "%s" has no BTS.' % n.subscriber,
                        status=status.HTTP_404_NOT_FOUND)
                # Strip the protocol field and just return the rest,
                # removing any trailing slash.
                bts_info = urlparse.urlparse(n.subscriber.bts.inbound_url)
                bts_netloc = bts_info.netloc
                bts_host = bts_info.hostname
                result = {
                    'netloc': bts_netloc,
                    'number': n.number,
                    'hostname': bts_host,
                    'source': n.kind,
                    'owner': n.network.id
                }
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response("No such number",
                                status=status.HTTP_404_NOT_FOUND)
        except Number.DoesNotExist:
            return Response("No such number", status=status.HTTP_404_NOT_FOUND)


class WhitelistAuthentication(BaseAuthentication):
    """A special authentication class that auths whitelisted BTS's."""

    def authenticate(self, request):
        """Implements a custom authentication scheme using a BTS uuid in the
        request and cross references it with a whitelist.

        Returns: (user, auth) if authentication succeeds or None if this scheme
                 is not attempted, and another authentication scheme should be
                 attempted

        Raises: AuthenticationFailed exception if an invalid or a
                non-whitelisted BTS uuid is provided
        """
        if "number" not in request.GET:
            # Not attempting whitelist auth scheme.
            return None
        try:
            query_number = request.GET["number"]
            number = Number.objects.get(number=query_number)
            if number.network.bypass_gateway_auth:
                return (number.network.auth_user, None)
            else:
                raise AuthenticationFailed("Number authentication failed.")
        except Number.DoesNotExist:
            raise AuthenticationFailed("Unknown number.")


class NumberAuth(APIView):
    """Verifies the owner of a particular number."""

    authentication_classes = (SessionAuthentication, TokenAuthentication,
                              WhitelistAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        if not "number" in request.GET:
            return Response("Missing number.",
                            status=status.HTTP_400_BAD_REQUEST)
        query_number = request.GET["number"]
        try:
            network = get_network_from_user(request.user)
            Number.objects.get(number=query_number,
                               network=network)
            return Response("OK", status=status.HTTP_200_OK)
        except Number.DoesNotExist:
            return Response(
                "Unauthorized", status=status.HTTP_401_UNAUTHORIZED)


class UUIDLookup(APIView):
    """Lookup BTS info like IP addr, port and the connected user.
    Security issues: this function allow determining what UUID is mapped to
    what user. Access should be restricted to internal requests only.

    WARNING: This is now DEPRECATED. Use the NumberAuth endpoint instead.
    """
    def get(self, request):

        logger.warning("Use of deprecated API call %s" % (request.GET, ))

        if "uuid" not in request.GET:
            return Response("No uuid specified.",
                            status=status.HTTP_400_BAD_REQUEST)
        query_num = request.GET["uuid"]
        try:
            network = get_network_from_user(request.user)
            bts = BTS.objects.get(uuid=query_num)
            # Strip the protocol field and just return the rest, removing any
            # trailing slash.
            bts_info = urlparse.urlparse(bts.inbound_url)
            result = {
                'netloc': bts_info.netloc,
                'hostname': bts_info.hostname,
                'owner': bts.network.id
            }
            return Response(result, status=status.HTTP_200_OK)
        except Number.DoesNotExist:
            return Response("No such UUID", status=status.HTTP_404_NOT_FOUND)


class BillVoice(APIView):
    """Handles voice billing for off-network events.

    Receives CDRs from our internal system.
    """

    def getText(self, nodelist):
        """Get the text value of an XML tag (from the minidom doc)."""
        rc = []
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        return ''.join(rc)

    def post(self, request, format=None):
        """Handle POST requests."""
        # First make sure the dom parses.
        try:
            dom = xml.dom.minidom.parseString(request.POST['cdr'])
        except xml.parsers.expat.ExpatError:
            logger.warning("invalid XML CDR: '%s'" % (request.POST['cdr'], ))
            return Response("Bad XML", status=status.HTTP_400_BAD_REQUEST)
        except KeyError:
            logger.warning("invalid POST request: '%s'" % (request.POST, ))
            return Response("Missing CDR", status=status.HTTP_400_BAD_REQUEST)
        # Then make sure all of the necessary pieces are there.  Fail if any
        # required tags are missing
        data = {}
        for tag_name in ["billsec", "username", "caller_id_name",
                         "network_addr", "destination_number"]:
            data[tag_name] = dom.getElementsByTagName(tag_name)
        for tag_name in data:
            if not data[tag_name]:
                return Response("Missing XML",
                                status=status.HTTP_400_BAD_REQUEST)
            else:
                data[tag_name] = self.getText(data[tag_name][0].childNodes)
        # Convert certain tags to ints.
        for tag_name in ["billsec"]:
            data[tag_name] = int(data[tag_name])
        # Try to get Number instances for both the caller and recipient.
        # If we find both Numbers in the system then a user on one Endaga
        # network is calling a subscriber on a different Endaga-managed
        # network, cool. In our cloud freeswitch instance we actually
        # "short circuit" this call so it never goes to Nexmo, but to the
        # operators the call is a regular incoming / outgoing event, so we
        # will bill it as such.
        caller_number, dest_number = None, None
        try:
            caller_number = Number.objects.get(number=data["caller_id_name"])
            try:
                caller_cost = caller_number.network.calculate_operator_cost(
                    'off_network_send', 'call',
                    destination_number=data['destination_number'])
            except ValueError as ex:
                # this is raised iff the destination has an invalid prefix
                logger.error("invalid number prefix: %s" % (ex, ))
                caller_cost = 0
            caller_number.network.bill_for_call(caller_cost,
                                                data['billsec'],
                                                'outside_call')
            logger.info("billed network '%s' for outgoing call: %d" %
                        (caller_number.network.name, caller_cost))
        except Number.DoesNotExist:
            pass
        try:
            dest_number = Number.objects.get(number=data["destination_number"])
            # cost to receive doesn't take source/caller into account
            dest_cost = dest_number.network.calculate_operator_cost(
                'off_network_receive', 'call')
            dest_number.network.bill_for_call(dest_cost,
                                              data['billsec'],
                                              'incoming_call')
            logger.info("billed network '%s' for incoming call: %d" %
                        (dest_number.network.name, dest_cost))
        except Number.DoesNotExist:
            pass
        if not (caller_number or dest_number):
            # We didn't find either Number, that's a failure.
            return Response("Invalid caller and destination",
                            status=status.HTTP_404_NOT_FOUND)

        # Local, incoming and outgoing calls respond with 200 OK.
        return Response("", status=status.HTTP_200_OK)
