"""Config (command) handlers for the federer server.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import gzip
import os
import threading

import dateutil.parser
import itsdangerous
import requests
import web

from ccm.common import logger
from core import events
from core import interconnect
from core.config_database import ConfigDB
from core.message_database import MessageDB
from core.subscriber import subscriber
from core.system_utilities import log_stream
from core.exceptions import SubscriberNotFound


class config(object):
    """Handles commands from the control server.

    General concept is that the control server makes a request, and this will
    dispatch to the proper handler.  For certain requests, this may in turn
    cause the client to issue a request back to the server (processing usage
    logs, for instance).
    """
    def __init__(self):
        self.conf = ConfigDB()
        self.msgid_db = MessageDB()
        self.ic = interconnect.endaga_ic(self.conf)

    def GET(self, command):
        """Handles get requests for certain commands."""
        valid_get_commands = ('req_usage', 'req_log', 'add_credit', 'req_checkin')
        if command not in valid_get_commands:
            return web.NotFound()
        d = web.input()
        if 'jwt' not in d:
            return web.BadRequest()
        try:
            data = self.check_signed_params(d['jwt'])
        except ValueError as e:
            logger.error("Value error dispatching %s" % (command,))
            return web.BadRequest(str(e))
        except Exception as e:
            logger.error("Other error dispatching %s: %s" % (command, str(e)))
            raise
        if command == "req_usage":  # NOTE: deprecated 2014oct23
            return self.req_checkin()
        if command == "req_log":
            return self.req_log(data)
        elif command == "add_credit":
            return self.adjust_credits(data)
        elif command == "req_checkin":
            return self.req_checkin()

    def POST(self, command):
        """Handles certain POST commands."""
        # Always send back these headers.
        headers = {
            'Content-type': 'text/plain'
        }
        # Validate the exact endpoint.
        valid_post_commands = ('deactivate_number', 'deactivate_subscriber')
        if command not in valid_post_commands:
            return web.NotFound()
        # Get the posted data and validate.  There should be a 'jwt' key with
        # signed data.  That dict should contain a 'number' key -- the one we
        # want to deactivate.
        data = web.input()
        jwt = data.get('jwt', None)
        if not jwt:
            return web.BadRequest()
        serializer = itsdangerous.JSONWebSignatureSerializer(
            self.conf['bts_secret'])
        try:
            jwt = serializer.loads(jwt)
        except itsdangerous.BadSignature:
            return web.BadRequest()
        if command == 'deactivate_number':
            if 'number' not in jwt:
                return web.BadRequest()
            # The params validated, deactivate the number.  ValueError is
            # raised if this is the subscriber's last number.
            # The number should correspond to an IMSI or give a 404
            try:
                imsi = subscriber.get_imsi_from_number(jwt['number'])
                subscriber.delete_number(imsi, jwt['number'])
            except SubscriberNotFound:
                return web.NotFound()
            except ValueError:
                return web.BadRequest()
            return web.ok(None, headers)
        elif command == 'deactivate_subscriber':
            if 'imsi' not in jwt:
                return web.BadRequest()
            # The number should correspond to an IMSI.
            try:
                subscriber.delete_subscriber(jwt['imsi'])
            except SubscriberNotFound:
                return web.NotFound()
            return web.ok(None, headers)

    def req_checkin(self):
        # Fire off a worker to send the checkin, then send back a 202.
        t = threading.Thread(target=self.checkin_worker)
        t.start()
        return web.Accepted()

    def req_log(self, data):
        PERMITTED_LOGS = ['endaga', 'syslog']
        required_fields = ["start", "end", "log_name"]
        if not all([_ in data for _ in required_fields]):
            return web.BadRequest()

        # By default there are no window start or end
        window_start = None
        window_end = None

        try:
            window_start = dateutil.parser.parse(data['start'])
        except ValueError:
            pass

        try:
            window_end = dateutil.parser.parse(data['end'])
        except ValueError:
            pass

        if data['log_name'] not in PERMITTED_LOGS:
            return web.BadRequest()

        logger.notice("Log %s requested by dashboard from %s to %s" %
                (data['log_name'], window_start or '-', window_end or '-'))
        t = threading.Thread(target=self.log_worker,
                args=(data['msgid'], window_start, window_end, data['log_name']))
        t.start()
        return web.Accepted()

    def log_worker(self, msgid, window_start, window_end, log_name):
        logger.info("Log req %s started" % msgid)
        log_path = "/var/log/%s" % log_name

        tmp_file = ('/tmp/%s-%s.log.gz' % (log_name, msgid))

        with gzip.open(tmp_file, 'w') as f:
            for msg in log_stream(log_path, window_start, window_end):
                f.write(msg)

        params = {
            'msgid': msgid,
            'log_name': log_name
        }
        files = {'file': open(tmp_file, 'rb')}
        r = requests.post(self.conf['registry'] + "/bts/logfile", data=params,
                         files=files, headers=self.ic.auth_header)
        try:
            if r.status_code == 200:
                logger.info("Log req %s posted successfully" % msgid)
            else:
                logger.error("Log req %s responded with %s: %s" % (msgid, r.status_code, r.text))
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error("Log req %s failed: %s" % (msgid, e))
        os.unlink(tmp_file)

    def checkin_worker(self):
        logger.notice("Endaga: Checkin requested by dashboard.")
        self.ic.checkin()

    def adjust_credits(self, data):
        required_fields = ["imsi", "change"]
        if not all([_ in data for _ in required_fields]):
            return web.BadRequest()
        imsi = data["imsi"]
        try:
            change = int(data["change"])
        except ValueError:
            return web.BadRequest()
        old_credit = subscriber.get_account_balance(imsi)
        if change > 0:
            subscriber.add_credit(imsi, str(abs(change)))
        elif change < 0:
            subscriber.subtract_credit(imsi, str(abs(change)))

        new_credit = subscriber.get_account_balance(imsi)

        # Codeship is stupid. These imports break CI and this is an untested
        # method :)
        from core import freeswitch_interconnect, freeswitch_strings

        # Send a confirmation to the subscriber
        number = subscriber.get_caller_id(imsi)
        change_frmt = freeswitch_strings.humanize_credits(change)
        balance_frmt = freeswitch_strings.humanize_credits(new_credit)

        fs_ic = freeswitch_interconnect.freeswitch_ic(self.conf)
        fs_ic.send_to_number(number, '000',
            freeswitch_strings.gt(
                "The network operator adjusted your credit by %(change)s. "
                "Your balance is now %(balance)s.") %
                {'change': change_frmt,
                 'balance': balance_frmt })

        # TODO(matt): all credit adjustments are of the kind "add_money," even
        #             if they actually subtract credit.
        reason = 'Update from web UI (add_money)'
        events.create_add_money_event(imsi, old_credit, new_credit, reason,
                                      to_number=number)
        return web.ok()

    def check_signed_params(self, jwt_data):
        """Checks a JWT signature and message ID.

        Decodes the params, makes sure they pass signature (i.e., are valid),
        and then checks that we haven't seen the msgid before.

        TODO(matt): refactor as this was copied from federer_handlers.common.
                    Inheriting from common as before does not work because CI
                    cannot import ESL, an import that comes from
                    freeswitch_interconnect.

        Raises:
          ValueError if there are errors

        Returns:
          True if everything checks out
        """
        s = itsdangerous.JSONWebSignatureSerializer(self.conf['bts_secret'])
        try:
            data = s.loads(jwt_data)
        except itsdangerous.BadSignature:
            logger.emergency("Bad signature for request, ignoring.")
            raise ValueError("Bad signature")
        # Make sure the msg hasn't been seen before, if so, discard it.
        if "msgid" in data:
            if self.msgid_db.seen(str(data['msgid'])):
                logger.error("Endaga: Repeat msgid: %s" % (data['msgid'],))
                raise ValueError("Repeat msgid: %s" % (data['msgid'],))
        else:
            logger.error("Endaga: No message ID.")
            raise ValueError("No message ID.")
        return data
