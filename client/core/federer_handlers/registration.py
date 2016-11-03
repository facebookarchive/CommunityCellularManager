"""Registration (provisioning) handlers for the federer server.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import threading
import traceback

import web

from ccm.common import logger
from core import events
from core import freeswitch_interconnect
from core import interconnect
from core.subscriber import subscriber
from core.config_database import ConfigDB
from core.federer_handlers.common import gt


class registration:
    """Class for doing registration.

    POST request fires off a registration worker, which allocates a new number,
    registers the phone, then sends the phone an SMS with the number.
    """
    def __init__(self):
        self.ic = None
        self.conf = ConfigDB()
        self.worker = self.registration_worker
        self.fs_ic = freeswitch_interconnect.freeswitch_ic(self.conf)

    def registration_worker(self, from_name, ip, port, ret_num):
        try:
            # Postcondition: number must be globally registered and set up.
            number = self.ic.register_subscriber(imsi=from_name)['number']
            subscriber.create_subscriber(from_name, number, ip, port)
            self.fs_ic.send_to_number(number, ret_num,
                    gt("Your number is %(number)s.") % {'number': number})
            reason = 'Provisioned user %s number %s' % (from_name, number)
            events.create_provision_event(from_name, reason)
        except Exception as e:
            self.fs_ic.send_to_imsi(from_name, ip, port, ret_num,
                    gt("Failed to register your handset."))
            logger.error("Failed to provision %s: %s" % (from_name,
                traceback.format_exc(e)))

    def POST(self):
        data = web.input()
        needed_fields = ["from_name", "ip", "port", "ret_num"]
        if all(i in data for i in needed_fields):
            from_name = str(data.from_name)
            ip = str(data.ip)
            port = str(data.port)
            ret_num = str(data.ret_num)
            params = {
                "from_name": from_name,
                "ip": ip,
                "port": port,
                "ret_num": ret_num
            }
            t = threading.Thread(target=self.worker, kwargs=params)
            t.start()
            raise web.Accepted()
        else:
            raise web.NotFound()


class endaga_registration(registration):

    def __init__(self):
        registration.__init__(self)
        self.ic = interconnect.endaga_ic(self.conf)
