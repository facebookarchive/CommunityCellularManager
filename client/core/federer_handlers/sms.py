"""Handles outgoing SMS and delivery receipts for the federer server.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import threading
import traceback

import requests
import web

from ccm.common import logger
from core import interconnect
from core.config_database import ConfigDB
from core.federer_handlers import common


class endaga_sms(common.incoming):
    """
    Class for handling incoming message from Endaga.
    """
    def __init__(self):
        common.incoming.__init__(self)

    def POST(self):
        """TODO (matt): need to verify: this is used by the dashboard only?
                        and is insecured?
        """
        # Always send back these headers.
        headers = {
            'Content-type': 'text/plain'
        }
        data = web.input()
        needed_fields = ["text", "to", "sender", "msgid"]
        if all(i in data for i in needed_fields):
            # Make sure we haven't already seen this message.
            if self.msgid_db.seen(str(data.msgid)):
                return data.msgid
            to = str(data.to)
            from_ = str(data.sender)
            body = str(data.text)
            self.fs_ic.send_to_number(to, from_, body)
            self.bill(to, from_)
            return web.ok(None, headers)
        else:
            return web.badrequest(None, headers)


class OutgoingSMSHandler(object):
    """Class for handling outgoing SMS messages.

    FS sends message data to this handler via POST.  We will start a thread to
    send the actual request.  If the request succeeds, we'll issue the billing
    request.

    This is needed due to poor chatplan performance.

    Returns response code 202 once we launch a thread to make the request to
    our API. Caller receives no further status updates, and there is no
    guarantee the SMS will actually be sent to our API.

    Returns a 404 if the request parameters are malformed.
    TODO(matt): make this return 400 instead, but first verify that nothing
    relies on the 404 behavior.


    Attributes:
        conf: a ConfigDB
        interconnect_client: the endaga interconnect client
        worker: a method that will be in its own thread and send the message
    """

    def __init__(self):
        self.conf = ConfigDB()
        self.interconnect_client = interconnect.endaga_ic(self.conf)
        self.worker = self.sms_worker

    def POST(self):
        """Handles POST requests."""
        data = web.input()
        needed_fields = ["to", "from_number", "from_name", "body",
                         "service_type"]
        if all(i in data for i in needed_fields):
            params = {
                "to": str(data.to),
                "from_num": str(data.from_number),
                "from_name": str(data.from_name),
                "body": str(data.body),
                "service_type": str(data.service_type)
            }
            t = threading.Thread(target=self.worker, kwargs=params)
            t.start()
            raise web.Accepted()
        else:
            raise web.NotFound()

    def sms_worker(self, to, from_num, from_name, body, service_type):
        """The SMS worker that runs in its own thread.

        Fails with a logger entry if we fail to post to the billing endpoint.

        Args:
            message params
        """
        try:
            # TODO(matt): handle else (message failed to send).
            if self.interconnect_client.send(to, from_num, body):
                billing_url = self.conf['billing_url']
                params = {
                    "from_name": from_name,
                    "from_number": from_num,
                    "destination": to,
                    "service_type": service_type
                }
                requests.post(billing_url, data=params)
        except Exception as e:
            logger.error("Endaga " + traceback.format_exc(e))
