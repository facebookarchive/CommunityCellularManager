# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
import json
import time

import requests
import snowflake

from ccm.common import delta, logger
from core import events
from core import number_utilities
from core import system_utilities
from core.subscriber import subscriber
from core.bts import bts
from core.checkin import CheckinHandler
from core.exceptions import BSSError
from gzip import GzipFile
from io import BytesIO


class endaga_ic(object):
    """Endaga interconnect."""

    MIN_COMPRESSIBLE_REQUEST_SZ = 512  # not much to gain compressing short str

    def __init__(self, conf):
        self.conf = conf
        self.token = conf['endaga_token']
        self.utilization_tracker = system_utilities.SystemUtilizationTracker()
        self._checkin_load_stats = {}
        self._session = None  # use persistent connection when possible
        self._session_cookies = None

    @property
    def auth_header(self):
        return {'Authorization': "Token %s" % self.token}

    @property
    def session(self):
        if not self._session:
            self._session = requests.Session()
        return self._session

    def _cleanup_session(self):
        if self._session:
            # make a best effort to close session, ignore any errors,
            # session may be in unexpected state after a network error
            # NOTE: we don't want to clean session cookies to let LBs
            # to provide "stickiness" while the server is healthy
            try:
                self._session.close()
            except BaseException:
                pass
        self._session = None

    def register_subscriber(self, imsi):
        """Send a request to the registry server with this BTS unique ID and
        the number.

        Raises: ValueError if the API failed to register the user
                400 - Bad parameters
                403 - User is not associated with this BTS
                404 - No numbers available
                409 - IMSI already registered to another network
                500 - Uh-oh
        """
        url = self.conf['registry'] + "/register/"
        try:
            r = requests.post(url,
                              headers=self.auth_header,
                              data={
                                  'imsi': imsi,
                                  'bts_uuid': snowflake.snowflake()
                              })
        except BaseException as e:  # log and rethrow
            logger.error("Endaga: Register network error: %s." % e)
            raise

        if r.status_code != 200:
            raise ValueError(r.text)

        return json.loads(r.text)

    def send(self, to, from_, body, to_country=None, from_country=None):
        """Send an SMS to our cloud API.

        Args:
            message params

        Returns:
            True if the message was accepted, False otherwise.
        """
        # Convert "to" to e.164 format.  We always add a plus, and
        # libphonenumber is smart enough to sort it out from there (even if
        # there's already a plus).
        message = {
            'from': from_,
            'to': number_utilities.convert_to_e164("+" + to, None),
            'body': body
        }
        # TODO(matt): use urlparse.urljoin here?
        endpoint = self.conf['registry'] + "/send/"
        try:
            r = requests.post(endpoint, headers=self.auth_header, data=message)
        except BaseException as e:  # log and rethrow as it was before
            logger.error("Endaga: Send SMS network error: %s." % e)
            raise

        return r.status_code == 202

    def checkin(self, timeout=11):
        """Gather system status."""

        # Compile checkin data
        checkin_start = time.time()
        status = {
            'usage': events.usage(),
            'uptime': system_utilities.uptime(),
            'system_utilization': self.utilization_tracker.get_data(),
        }

        # Append status if we can
        try:
            #get the software versions
            status['versions'] = bts.get_versions()
        except BSSError as e:
            logger.error("bts get_versions error: %s" % e)

        try:
            # Gather camped subscriber list
            status['camped_subscribers'] = bts.active_subscribers()
        except BSSError as e:
            logger.error("bts get active_subscribers error: %s" % e)

        # Gather tower load and noise data.
        # NOTE(matt): these values can vary quite a bit over a minute. It
        #       might be worth capturing data more frequently and sending
        #       something like average or median values.
        status['openbts_load'] = {}
        try:
            status['openbts_load'] = bts.get_load()
        except BSSError as e:
            logger.error("bts get_load error: %s" % e)

        for key, val in list(self._checkin_load_stats.items()):
            status['openbts_load']['checkin.' + key] = val
        self._checkin_load_stats.clear()

        try:
            status['openbts_noise'] = bts.get_noise()
        except BSSError as e:
            logger.error("bts get_noise error: %s" % e)

        status['radio'] = {}
        try:
            status['radio']['band'] = bts.get_band()
            # eventually need to also grab all used channels, not just c0
            # TODO: (kheimerl) T13270338 Add multiband support
            status['radio']['c0'] = bts.get_arfcn_c0()
            #also add power here eventually
            # TODO: (kheimerl) T13270365 Add power level support
        except BSSError as e:
            #delete the key if this failed
            del status['radio']
            logger.error("bts radio error: %s" % e)

        # Add balance sync data
        status['subscribers'] = subscriber.get_subscriber_states(
            imsis=events.EventStore().modified_subs())

        # Add delta protocol context (if available) to let server know,
        # client supports delta optimization & has a prior delta state
        if delta.DeltaProtocol.CTX_KEY not in status:  # just a precaution
            sections_ctx = {}
            for section, ctx in list(CheckinHandler.section_ctx.items()):
                if ctx:
                    sections_ctx[section] = ctx.to_proto_dict()

            if sections_ctx:
                status[delta.DeltaProtocol.CTX_KEY] = {
                    delta.DeltaProtocolOptimizer.SECTIONS_CTX_KEY: sections_ctx
                }

        # Send checkin request.
        uuid = snowflake.snowflake()
        data = {
            'status': status,
            'bts_uuid': uuid,
        }
        headers = dict(self.auth_header)
        # Set content type to app/json & utf-8, compressed or not - JSON should
        # be more efficient then URL encoded JSON form payload
        headers['Content-Type'] = 'application/json; charset=utf-8'
        data_json = json.dumps(data)
        decompressed_status_len = len(data_json)
        status_len = decompressed_status_len

        if status_len > endaga_ic.MIN_COMPRESSIBLE_REQUEST_SZ:
            # try to gzip payload, send uncompressed if compression failed
            try:
                gzbuf = BytesIO()
                with GzipFile(mode='wb', fileobj=gzbuf) as gzfile:
                    gzfile.write(bytes(data_json, encoding='UTF-8'))
                data_json = gzbuf.getvalue()
                # Using Content-Encoding header since AWS cannot handle
                # Transfer-Encoding header which would be more appropriate here
                headers['Content-Encoding'] = 'gzip'
                status_len = len(data_json)  # set len to reflect compression
            except BaseException as e:
                logger.error("Checkin request Gzip error: %s" % e)

        headers['Content-Length'] = str(status_len)

        post_start = time.time()
        try:
            r = self.session.post(self.conf['registry'] + "/checkin?id=" +
                                  # add part of uuid to the query, it helps with
                                  # debugging & server side logging and can
                                  # be used by LBs
                                  uuid[:8],
                                  headers=headers,
                                  data=data_json,
                                  timeout=timeout,
                                  cookies=self._session_cookies)

        except BaseException as e:
            logger.error("Endaga: checkin failed , network error: %s." % e)
            self._cleanup_session()
            self._checkin_load_stats['req_sz'] = status_len
            self._checkin_load_stats['raw_req_sz'] = decompressed_status_len
            self._checkin_load_stats['post_lat'] = time.time() - post_start
            raise

        post_end = time.time()

        # Make sure either server sent charset or we set it to utf-8 (JSON
        # default)
        if not r.encoding:
            r.encoding = 'utf-8'

        text = r.text
        decompressed_response_len = len(text)
        response_len = decompressed_response_len

        # Try to get correct content length from HTTP headers, it should
        # reflect correctly compressed length. if it fails - fall back to
        # getting length of returned text
        cont_len = r.headers.get('Content-Length')
        if cont_len:
            try:
                response_len = int(cont_len)
            except BaseException:
                pass

        if r.status_code == 200:
            try:
                CheckinHandler(text)
                logger.info("Endaga: checkin success.")
                if r.cookies is not None:
                    if self._session_cookies is None:
                        # First time cookies are seen from server
                        # initialize the cookies dict
                        self._session_cookies = dict(r.cookies)
                    else:
                        for key, value in r.cookies.items():
                            # if server sent new/updated cookies, update them,
                            # but keep previously set cokies as well. ELBs
                            # do not send AWSELB cookies on every request &
                            # expect clients to 'remember' them
                            self._session_cookies[key] = value
            except BaseException:
                self._cleanup_session()
                raise
        else:
            logger.error("Endaga: checkin failed (%d), reason: %s, body: %s" %
                         (r.status_code, r.reason, r.text))
            # cleanup session on any error
            if r.status_code >= 300:
                self._cleanup_session()

        checkin_end = time.time()

        self._checkin_load_stats['req_sz'] = status_len  # request payload SZ
        self._checkin_load_stats['raw_req_sz'] = decompressed_status_len
        self._checkin_load_stats['rsp_sz'] = response_len  # response payload SZ
        self._checkin_load_stats['raw_rsp_sz'] = decompressed_response_len
        # Checkin Latencies
        self._checkin_load_stats['post_lat'] = post_end - post_start
        self._checkin_load_stats['process_lat'] = checkin_end - post_end
        self._checkin_load_stats['lat'] = checkin_end - checkin_start

        data['response'] = {'status': r.status_code, 'text': r.text}
        return data
