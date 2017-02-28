"""Views to handle our API.

API from old registry server:
    ('/register/(.*)/(.*)/', Register), --> Register.post
    ('/disown/(.*)/(.*)/', Disown), --> Register.delete (or put?)
    ('/fetch/(.*)/', GetNumber), --> Register.get
    ('/check/(.*)/', Check), --> Number.get
    ('/receipt/', DeliveryReceipt),
    ('/bts/(.*)/', BtsConfig),

Old API description:
    GetNumber.get: Return an available number (if none, client buys a number
                   from Nexmo directly)
    Register.get: Set number to 'pending' state for a given BTS
    Register.delete: Set number to 'available' state
    Disown.delete: Remove number from registry completely
    Check.get: Get the number, BTS, state, and timestamp for a number (Number
               detail view, really); no longer needed

This is a crappy API, just written for backwards compatibility with the
existing client code (the old API was a quick hack and designed around having
the BTS interact as directly as possible with upstream providers). Several
parts of this API aren't really needed anymore since we handle a lot of edge
cases in number registration on the server side.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import (TokenAuthentication,
                                           SessionAuthentication)
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.http import QueryDict
from django.middleware.gzip import GZipMiddleware

from endagaweb import checkin
from endagaweb import models
from endagaweb.ic_providers.nexmo import NexmoProvider
from endagaweb.ic_providers.kannel import KannelProvider
# TODO(matt): figure out why tests break when the serializers import is
#             removed.  It's especially weird because that module is unused.
from endagaweb.util.api import get_network_from_user
from endagaweb import serializers
from endagaweb import tasks

import json
import requests
import time
import uuid
import re
from gzip import GzipFile
from io import BytesIO

# Response compressor for use by Checkin and possibly other handlers
gzip_middleware = GZipMiddleware()

# Minimal size of response payload to be considered for compression
# std django middleware compresses payload over 200 bytes long (too short for
# a reasonable gzip gain)
MIN_COMPRESSIBLE_RESPONSE_SZ = 512

# Compiled Regexes for fast HTTP header lookups
RE_INCLUDES_GZIP = re.compile(r'\bgzip\b')
RE_INCLUDES_APP_JSON = re.compile(r'\bapplication/json\b')
RE_INCLUDES_APP_FORM = re.compile(r'\bapplication/x-www-form-urlencoded\b')


# Exception classes to be mapped to corresponding HTTP status codes
class HTTP_415_Error(Exception):
    pass


class HTTP_422_Error(Exception):
    pass


class Register(APIView):
    """Handles subscriber registration with a given BTS.

    /GET (OLD API)
        A user can only register a number they own to a BTS they own.  Numbers
        must already exist in the system.

        The registration request must include the subscriber's IMSI, the number
        we intend to register them with, and the current BTS they are on. This
        registration request fails if the IMSI is already in the database, or
        if the number is already in use.

        TODO(matt): adjust this slightly since we are no longer associating
        numbers with BTS but with Networks?

        An example request:
          GET /<bts_uuid>/<number>/?imsi=IMSI000123

    /POST (NEW ONE-STEP SUBSCRIBER REGISTRATION ENDPOINT)


    /DELETE
        Request from a BTS to delete a number and mark it as available.
    """

    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)
    renderer_classes = (JSONRenderer,)

    def post(self, request, format=None):
        """ Request a number and associate with a subscriber. """
        if not ("bts_uuid" in request.POST or "imsi" in request.POST):
            return Response("", status=status.HTTP_400_BAD_REQUEST)

        bts_uuid = str(request.POST['bts_uuid'])
        imsi = str(request.POST['imsi'])
        if not re.match('^IMSI\d{14,15}$', imsi):
            return Response("Invalid IMSI", status=status.HTTP_400_BAD_REQUEST)

        network = get_network_from_user(request.user)
        try:
            bts = models.BTS.objects.get(uuid=bts_uuid,
                                         network=network)
        except models.BTS.DoesNotExist:
            return Response("User is not associated with that BTS.",
                            status=status.HTTP_403_FORBIDDEN)

        # If the IMSI is already in use, and associated with another network,
        # prevent the registration of a new number. If it's associated with
        # this network, simply return the currently-associated number. N.B.,
        # this effectively enforces a 1-1 mapping of subscriber to number
        # currently.
        try:
            subscriber = models.Subscriber.objects.get(imsi=imsi)
            if subscriber.network != network:
                return Response("IMSI already registered to another network",
                                status=status.HTTP_409_CONFLICT)
        except models.Subscriber.DoesNotExist:
            # Create a new subscriber if one matching this IMSI didn't already
            # exist.
            subscriber = models.Subscriber(network=network, imsi=imsi,
                                           balance=0, bts=bts)
            subscriber.save()

        # If the subscriber already exists, we should return the associated
        # phone number and update the BTS to match what is being used.
        n = models.Number.objects.filter(subscriber=subscriber).first()
        if not n: # Otherwise, pick a random available number and associate it.
            with transaction.atomic():
                n = models.Number.objects.filter(state="available",
                        country_id=network.number_country).first()

                if not n:
                    return Response("No number available",
                                    status=status.HTTP_404_NOT_FOUND)

                n.state = "inuse"
                n.network = network
                n.subscriber = subscriber
                n.save()
                n.charge()

        return Response({'number': n.number, 'subscriber': subscriber.imsi,
                         'balance': subscriber.balance},
                        status=status.HTTP_200_OK)


    def get(self, request, bts_uuid=None, number=None, format=None):
        """ Associate a number to a BTS.

        DEPRECATED (shasan 2016jan5) -- use the POST endpoint instead
        """
        if not (number or bts_uuid or "imsi" in request.GET):
            return Response("", status=status.HTTP_400_BAD_REQUEST)
        network = get_network_from_user(request.user)
        try:
            bts = models.BTS.objects.get(uuid=bts_uuid,
                                         network=network)
        except models.BTS.DoesNotExist:
            return Response("User is not associated with that BTS.",
                            status=status.HTTP_403_FORBIDDEN)
        # If the IMSI is already in use, and associated with another BTS,
        # prevent the registration of a new number.  However, we allow IMSIs
        # to register a second number on the IMSI's original BTS.
        imsi = request.GET['imsi']
        try:
            subscriber = models.Subscriber.objects.get(imsi=imsi)
            if subscriber.network != network:
                return Response("IMSI already registered",
                                status=status.HTTP_409_CONFLICT)
        except models.Subscriber.DoesNotExist:
            # Create a new subscriber if one matching this IMSI didn't already
            # exist.
            subscriber = models.Subscriber(network=network, imsi=imsi,
                                           balance=0, bts=bts)
            subscriber.save()

        with transaction.atomic():
            q = models.Number.objects.filter(number__exact="%s" % number)
            if len(q) > 0:
                n = q[0]
                # This is tricky. Numbers that get marked 'pending' will have
                # the network id already set, so this check fails and we set
                # the number as in-use. This is an artifact of the two-step
                # number registration process. So don't remove the network ID
                # check!
                if n.state != "available" and n.network != bts.network:
                    return Response("Number already in use.",
                                    status=status.HTTP_400_BAD_REQUEST)
                n.network = bts.network
                n.state = "inuse"
            else:
                # FIXME this should never happen -- all numbers should already
                # be in the system, unless we're associating an old BTS for the
                # first time (like w/ Bok)
                n = models.Number(number=number, state="inuse",
                                  network=bts.network)
            # Associate it with the subscriber and save.
            n.subscriber = subscriber
            n.save()
            return Response(None, status=status.HTTP_200_OK)


    def delete(self, request, bts_uuid=None, number=None, format=None):
        """ Dis-associate a number from a BTS and mark it available. """
        if not (number or bts_uuid):
            return Response("", status=status.HTTP_400_BAD_REQUEST)
        network = get_network_from_user(request.user)
        try:
            bts = models.BTS.objects.get(uuid=bts_uuid,
                                         network=network)
        except models.BTS.DoesNotExist:
            return Response("User is not associated with that BTS.",
                            status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            q = models.Number.objects.filter(number__exact=number).filter(
                network=bts.network)
            for number in q:
                number.state = "available"
                number.network = None
                number.subscriber = None
                number.save()
                return Response(None, status=status.HTTP_200_OK)
            return Response(None, status=status.HTTP_404_NOT_FOUND)


class GetNumber(APIView):
    """Gets a number for a sub from the DB or from a provider."""

    # CURRENTLY BROKEN FOR NON-NEXMO NUMBERS -Kurtis
    # https://github.com/endaga/endaga-web/issues/406

    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request, bts_uuid=None, format=None):
        """Return a number that's usable by a BTS.

        We first check for "available" numbers in our database. If there are
        none, we buy a number from a provider, set it up, and return here. We
        have to specify a specific BTS to avoid a race condition when multiple
        BTS register for a number at once.
        """
        if not bts_uuid:
            return Response("No BTS UUID specified.",
                            status=status.HTTP_400_BAD_REQUEST)
        network = get_network_from_user(request.user)
        try:
            bts = models.BTS.objects.get(uuid=bts_uuid,
                                         network=network)
        except models.BTS.DoesNotExist:
            return Response("The specified BTS does not belong to the user.",
                            status=status.HTTP_403_FORBIDDEN)
        # First check for available numbers.  If a number is available, it's up
        # for grabs by anyone.
        with transaction.atomic():
            q = models.Number.objects.filter(state__exact="available")
            for n in q:
                # We do this here rather than in the db query since at this
                # time some numbers don't have a country field to query on. Can
                # probably be removed later. -- SH (2014 aug 21)
                # TODO(matt): this potentially sets a lot of numbers as
                #             pending..
                if n.country() == network.number_country:
                    n.state = "pending"
                    n.network = network
                    n.save()
                    n.charge()
                    return Response(int(n.number), status=status.HTTP_200_OK)

        # No number available, so we have to buy one from Nexmo.
        # TODO: Try to buy from multiple vendors
        np = NexmoProvider(settings.ENDAGA['NEXMO_ACCT_SID'],
                           settings.ENDAGA['NEXMO_AUTH_TOKEN'],
                           settings.ENDAGA['NEXMO_INBOUND_SMS_URL'],
                           None, #outbound_sms_url
                           settings.ENDAGA['NEXMO_INBOUND_VOICE_HOST'],
                           country=network.number_country)
        try:
            # This call creates the new number in the DB as a side effect.
            new_number = np.get_number(bts.network)
            print "New number is %s" % new_number
            return Response(new_number, status=status.HTTP_200_OK)
        except ValueError:
            return Response("Number not available",
                            status=status.HTTP_404_NOT_FOUND)


class SendSMS(APIView):
    """API handler for sending SMS"""
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    #todo: make config -kurtis
    HANDLERS = {'number.nexmo.monthly'   : (NexmoProvider,
                                            settings.ENDAGA['NEXMO_ACCT_SID'],
                                            settings.ENDAGA['NEXMO_AUTH_TOKEN'],
                                            settings.ENDAGA['NEXMO_INBOUND_SMS_URL'],
                                            None, #outbound sms_url
                                            settings.ENDAGA['NEXMO_INBOUND_VOICE_HOST']),
                'number.telecom.permanent' : (KannelProvider,
                                              settings.ENDAGA['KANNEL_USERNAME'],
                                              settings.ENDAGA['KANNEL_PASSWD'],
                                              None, #inbound sms_url
                                              settings.ENDAGA['KANNEL_OUTBOUND_SMS_URL'],
                                              None)
            }

    def post(self, request, format=None):
        """POST handler."""
        from_ = str(request.POST['from'])
        to_ = str(request.POST['to'])
        body = str(request.POST['body'])
        network = get_network_from_user(request.user)
        if network.billing_enabled and network.ledger.balance <= 0:
            # Shouldn't this be a 402 payment required? -kurtis
            return Response("operator has no credit in Endaga account",
                            status=status.HTTP_400_BAD_REQUEST)
        q = models.Number.objects.get(number=from_)
        if (q.kind not in SendSMS.HANDLERS):
            #shouldn't this be a 404 not found? -kurtis
            return Response("Invalid sending number",
                            status=status.HTTP_400_BAD_REQUEST)
        else:
            provider = SendSMS.HANDLERS[q.kind][0](
                SendSMS.HANDLERS[q.kind][1], #username
                SendSMS.HANDLERS[q.kind][2], #password
                SendSMS.HANDLERS[q.kind][3], #inbound_sms
                SendSMS.HANDLERS[q.kind][4], #outbound_sms
                SendSMS.HANDLERS[q.kind][5]) #inbound_voice
            try:
                provider.send(to_,from_,body)
            except Exception:
                message = '%s to: %s, from: %s, body len: %s' % (
                    provider, to_, from_, len(body))
                raise Exception(message)
            # Bill the operator.
            cost_to_operator = network.calculate_operator_cost(
                'off_network_send', 'sms', destination_number=to_)
            network.bill_for_sms(cost_to_operator, 'outside_sms')
            return Response("", status=status.HTTP_202_ACCEPTED)

class InboundSMS(APIView):
    # TODO eventually, one for each incoming provider (really, eventually, that
    # should be extracted into a service, behind a LB).
    # No authentication because anyone can send us an SMS.

    #kannel better supports GET
    def get(self, request, format=None):
        return self.handle_sms(request.GET, format)

    #Nexmo is configured to use POST for correctness's sake
    def post(self, request, format=None):
        return self.handle_sms(request.POST, format)

    def handle_sms(self, request, format=None):
        needed_fields = ["text", "to", "msisdn"]
        if all(i in request for i in needed_fields):
            to_number = request['to']
            from_ = request['msisdn']
            body = request['text']
            msgid = str(uuid.uuid4())
            # Lookup the BTS inbound_url.
            q = models.Number.objects.filter(number__exact=to_number)
            if len(q) > 0:
                n = q[0]
                if not n.subscriber:
                    print "no subscriber for number %s" % n.number
                    return Response('No associated subscriber.',
                                    status=status.HTTP_404_NOT_FOUND)
                bts = n.subscriber.bts
                if not bts:
                    print "no BTS for number %s" % n.number
                    return Response("No such number.",
                                    status=status.HTTP_404_NOT_FOUND)
                url = bts.inbound_url + "/endaga_sms"
                params = {
                    'to': to_number,
                    'sender': from_,
                    'text': body,
                    'msgid': msgid
                }
                tasks.async_post.delay(url, params)
                # Bill the operator.
                cost_to_operator = bts.network.calculate_operator_cost(
                    'off_network_receive', 'sms')
                n.network.bill_for_sms(cost_to_operator, 'incoming_sms')
                return Response("", status=status.HTTP_200_OK)
            else:
                print "no such number %s" % to_number
                return Response("No such number.",
                                status=status.HTTP_404_NOT_FOUND)
        elif not any(i in request for i in needed_fields):
            # Needed for nexmo to accept this url.
            print "test ok"
            return Response("", status=status.HTTP_200_OK)
        else:
            print "bad InboundSMS request: %s" % request
            return Response("", status=status.HTTP_400_BAD_REQUEST)


class InboundReceipt(APIView):
    """Handle inbound SMS delivery receipts."""
    def post(self, request, format=None):
        needed_fields = ["status", "to", "msisdn"]
        if all(i in request.POST for i in needed_fields):
            to = str(request.POST['to'])
            from_ = str(request.POST['msisdn'])
            rstatus = str(request.POST['status'])
            msgid = str(uuid.uuid4())
            q = models.Number.objects.filter(number__exact=to)
            if len(q) > 0:
                n = q[0]
                if not n.subscriber:
                    return Response("Number isn't attached to a subscriber.",
                                    status=status.HTTP_404_NOT_FOUND)
                if n.subscriber.bts:
                    url = n.subscriber.bts.inbound_url + "/nexmo_delivery"
                    params = {
                        'to': to,
                        'msisdn': from_,
                        'status': rstatus,
                        'msgid': msgid,
                    }
                    tasks.async_get.delay(url, params)
                    return Response("", status=status.HTTP_200_OK)
                else:
                    return Response("Subscriber not camped.",
                                    status=status.HTTP_404_NOT_FOUND)
            else:
                return Response(
                    "No such number.", status=status.HTTP_404_NOT_FOUND)
        else:
            return Response("", status=status.HTTP_400_BAD_REQUEST)


class UTF8JSONRenderer(JSONRenderer):
    """
    JSONRenderer doesn't set charset, it results in client decoding
    JSON Utf-8 encoded strings using default decoders mangling international
    names.
    UTF8JSONRenderer adds charset = 'utf-8' to std JSONRenderer
    """
    charset = 'utf-8'


class Checkin(APIView):
    """Handles the BTS checkin.

    It accepts status information, passes that along to the proper handlers,
    and then returns configuration data.

    Status must be passed in as a plain JSON dictionary. The response will be
    in the format:

        {
         'response': <plain json response>,
        }

    """
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)
    renderer_classes = (UTF8JSONRenderer,)

    @staticmethod
    def _process_post_data(request):
        """
        Helper function to handle POST payload decoding & decompression
        Args:
            request: rest_framework Request object

        Returns: tuple (BTS UUID, status dict)

        """
        transfer_enc = request.META.get('HTTP_TRANSFER_ENCODING', '')
        content_enc = request.META.get('HTTP_CONTENT_ENCODING', '')
        content_type = request.content_type

        # Check for both headers: Transfer-Encoding & Content-Encoding
        # While Transfer-Encoding would be preferable here, AWS cannot
        # handle it for now
        if ((transfer_enc and RE_INCLUDES_GZIP.search(transfer_enc)) or
                (content_enc and RE_INCLUDES_GZIP.search(content_enc))):
            try:
                # uncompress if Transfer Encoding: gzip header is present
                gzfio = BytesIO(request.body)
                gzf = GzipFile(fileobj=gzfio)
                post_data = gzf.read()
            except BaseException as e:
                message = "Checkin Gzip Exception: %s" % e
                print(message)
                raise HTTP_422_Error(message)

            if content_type:
                try:
                    if RE_INCLUDES_APP_FORM.search(content_type):
                        # if form data was compressed, we need to parse it again
                        # since std djngo form handler won't be able to
                        form_post_data = QueryDict(post_data,
                                                   encoding=request.encoding)
                        return (form_post_data['bts_uuid'],
                                json.loads(form_post_data['status']))
                    elif RE_INCLUDES_APP_JSON.search(content_type):
                        data_json = json.loads(post_data)
                        return data_json['bts_uuid'], data_json['status']

                except BaseException as e:
                    message = "Checkin Gzipped JSON Parsing Exception: %s" % e
                    print(message)
                    raise HTTP_422_Error(message)

                message = 'Invalid Checkin Content Type %s' % content_type
                print(message)
                raise HTTP_415_Error(message)

        # No compression or uncompressed by a proxy server, etc.
        if content_type and RE_INCLUDES_APP_JSON.search(content_type):
            try:
                data_json = json.loads(request.body)
                return data_json['bts_uuid'], data_json['status']
            except BaseException as e:
                message = "Checkin JSON Parsing Exception: %s" % e
                print(message)
                raise HTTP_422_Error(message)

        # Original codepath for legacy clients
        return request.POST['bts_uuid'], json.loads(request.POST['status'])

    def post(self, request):
        """Handles POST requests."""

        try:
            bts_uuid, bts_status = self._process_post_data(request)
        except HTTP_415_Error as e:
            return Response(str(e),
                            status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        except HTTP_422_Error as e:
            return Response(str(e),
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (ValueError, KeyError):
            return Response("Invalid/missing checkin parameters.",
                            status=status.HTTP_400_BAD_REQUEST)

        # See if this BTS has been deregistered.
        try:
            dbts = models.DeregisteredBTS.objects.get(uuid=bts_uuid)
            resp = {
                'status': 'deregistered',
            }
            dbts.delete()
            return Response({'response': resp}, status=status.HTTP_200_OK)
        except models.DeregisteredBTS.DoesNotExist:
            pass
        # The BTS isn't deregistered, continue with the checkin as normal.
        network = get_network_from_user(request.user)
        try:
            bts = models.BTS.objects.get(uuid=bts_uuid,
                                         network=network)
        except models.BTS.DoesNotExist:
            return Response("Incorrect auth for BTS.",
                            status=status.HTTP_403_FORBIDDEN)

        try:
            resp = checkin.CheckinResponder(bts).process(bts_status)
        except Exception as e:
            print "Error handling checkin (BTS %s): %s" % (bts.uuid, e)
            print "BTS status: %s" % bts_status
            raise

        checkin_resp = Response({'response': resp}, status=status.HTTP_200_OK)

        def gzip_response_callback(response):
            if len(response.content) < MIN_COMPRESSIBLE_RESPONSE_SZ:
                return response
            gzipped_resp = gzip_middleware.process_response(request, response)
            return gzipped_resp

        checkin_resp.add_post_render_callback(gzip_response_callback)
        return checkin_resp

class SSLConfig(APIView):
    renderer_classes = (JSONRenderer,)
    """ We don't do authentication for this, as no request made here will be
    sensitive. We dump all requests with BTS UUIDs that haven't been added
    already. """
    def get(self, request, format=None):
        """
        Submit a UUID and get back an API key and an OpenSSL conf.
        """
        bts_uuid = request.GET['bts_uuid']

        try:
            bts = models.BTS.objects.get(uuid=bts_uuid)
        except models.BTS.DoesNotExist:
            return Response("Unknown BTS",
                            status=status.HTTP_404_NOT_FOUND)

        # if the BTS is added but not registered, return OpenSSL configuration
        # data and api key.
        # NOTE: This check is security sensitive! We cannot allow a BTS that
        # has already registered to receive the API key for an account. Doing
        # so would enable an attacker who learns the UUID of a BTS to issue API
        # requests on behalf of the account holder. With this check, this
        # attack is only possible between the time that a user adds a BTS to
        # their account and when that BTS checks in.
        if bts.needs_vpnconf():
            resp = {}
            resp['token'] = str(bts.network.api_token)
            resp['sslconf'] = self.get_openssl_conf(bts)
            return Response(resp, status=status.HTTP_200_OK)
        else:
            return Response("Registered already",
                            status=status.HTTP_403_FORBIDDEN)

    def get_openssl_conf(self, bts):
        """
        Generates an OpenSSL conf. The common name (CN) for the
        client is a combination of uuid + server time when this was
        called. This ensurces a unique CN for the backend certifier
        service. Most recent CN is the only valid one (others can be
        safely and automatically added to the CRL).
        """
        user_profiles = models.UserProfile.objects.filter(network=bts.network)
        data = {
            'account_id': bts.network.api_token,
            'bts_cn': "%s-%s" % (bts.uuid, int(time.time())),
            # Who is a network point of contact?
            'account_email': settings.TEMPLATE_CONSTANTS['SUPPORT_EMAIL'],
        }
        return render_to_string("internal/opensslconf.html", data)

class BTSLogfile(APIView):
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)

    def post(self, request, format=None):
        required_fields = ['msgid', 'log_name']
        network = get_network_from_user(request.user)
        if not all([_ in request.POST for _ in required_fields]):
            return Response("Missing fields",
                            status=status.HTTP_400_BAD_REQUEST)

        if not 'file' in request.FILES:
            return Response("Missing file",
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            log_req = models.BTSLogfile.objects.get(uuid=request.POST['msgid'])
        except models.BTSLogfile.DoesNotExist:
            return Response("Unknown request.",
                            status=status.HTTP_400_BAD_REQUEST)

        if log_req.bts.network != network:
            return Response("Unauthorized.",
                            status=status.HTTP_403_FORBIDDEN)

        log_req.logfile=request.FILES['file']
        log_req.status = 'done'
        log_req.save()

        return Response("OK", status=status.HTTP_200_OK)


class BTSRegistration(APIView):
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = (IsAuthenticated,)
    renderer_classes = (JSONRenderer,)

    def get(self, request, format=None):
        """
        Update the current inbound URL, and return registration status.
        """
        if not all([_ in request.GET for _ in ['bts_uuid', 'vpn_status', 'vpn_ip']]):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        bts_uuid = request.GET['bts_uuid']
        vpn_up = request.GET['vpn_status'] == "up"
        vpn_ip = request.GET['vpn_ip']

        # Old versions of client didn't specify this, but always ran on port
        # 8081, so assume that as default.
        federer_port = request.GET.get('federer_port', "8081")

        network = get_network_from_user(request.user)
        try:
            bts = models.BTS.objects.get(uuid=bts_uuid,
                                         network=network)
        except models.BTS.DoesNotExist:
            return Response({"status": "BTS isn't registered."},
                            status=status.HTTP_403_FORBIDDEN)

        # we know the bts has the right token if it's authed, so provide the secret
        # TODO: cycle this to a random code
        if not bts.secret:
            bts.secret = bts.uuid
            bts.save()

        if bts.is_registered() and vpn_up:
            inbound = self.update_inbound_url(bts, vpn_ip, federer_port)
            bts.save()
            return Response({'status': 'registered, ok',
                             'inbound': inbound,
                             'bts_secret': bts.secret},
                            status=status.HTTP_200_OK)
        elif vpn_up:
            # the BTS reports the VPN is up, and has authed w/ API key,
            #so we consider the BTS fully reigstered.
            bts.mark_registered()
            bts.mark_active()
            inbound = self.update_inbound_url(bts, vpn_ip, federer_port)
            bts.save()
            return Response({'status': 'unregistered -> registered',
                             'inbound': inbound, 'bts_secret': bts.secret},
                            status=status.HTTP_200_OK)
        else:
            # TODO: add logic to handle lack of inbound URL
            return Response("", status=status.HTTP_404_NOT_FOUND)

    def post(self, request, format=None):
        """
        Submit a CSR for signing, and get back a signed cert
        as well as an OpenVPN conf.
        """
        if not all([_ in request.POST for _ in ['bts_uuid', 'csr']]):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        bts_uuid = request.POST['bts_uuid']
        csr = request.POST['csr']

        network = get_network_from_user(request.user)
        try:
            bts = models.BTS.objects.get(uuid=bts_uuid,
                                         network=network)
        except models.BTS.DoesNotExist:
            return Response({"status": "BTS isn't registered."},
                            status=status.HTTP_403_FORBIDDEN)

        r = requests.post('http://%s/csr' % settings.ENDAGA['KEYMASTER'],
                          data={'ident': bts_uuid, 'csr': csr})
        if r.status_code == 200:
            cert = json.loads(r.content)['certificate']
            bts = models.BTS.objects.get(uuid=bts_uuid)
            bts.certificate=cert
            bts.save()
            vpnconf = self.get_vpn_conf(bts)

            return Response({'certificate': cert, 'vpnconf': vpnconf},
                            status=status.HTTP_200_OK)
        else:
            return Response("status: %d" % (r.status_code,),
                            status=status.HTTP_400_BAD_REQUEST)

    def update_inbound_url(self, bts, vpn_ip, federer_port):
        """ Wrapper for updating BTS inbound. DOES NOT SAVE """
        # XXX DANGER ZONE
        # We used to just care about the "inbound url" of a BTS --
        # specifically the IP that we could hit the client's inbound SMS
        # url at. We now use this field as the basis for other stuff,
        # such as the inbound SIP address. In the future we should
        # only store the network location of the BTS itself, and build a
        # URL or whatever else we need elsewhere. Additionally, early versions
        # of client ran their web server on port 8081; we now run on port 80 by
        # default. New versions that use port 80 and above specify what port
        # they are running with in the BTS registration, so we can assume 8081
        # unless otherwise stated.
        bts.inbound_url = "http://%s:%s" % (vpn_ip, federer_port)
        return bts.inbound_url

    def get_vpn_conf(self, bts):
        return render_to_string("internal/openvpn_client_conf.html",
                {'vpn_server_ip': settings.ENDAGA['VPN_SERVER_IP']})
