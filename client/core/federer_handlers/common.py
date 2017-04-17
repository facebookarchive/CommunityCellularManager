"""Common utils in the federer server.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import gettext
import traceback

import itsdangerous

from ccm.common import logger
from core import billing
from core import events
from core import freeswitch_interconnect
from core.subscriber import subscriber
from core.config_database import ConfigDB
from core.message_database import MessageDB


cdb = ConfigDB()
gt = gettext.translation(
    "endaga", cdb['localedir'], [cdb['locale'], "en"]).gettext
# Hardcode the dashboard's from_number.
DASHBOARD_FROM_NUMBER = '0000'


class incoming(object):
    def __init__(self):
        self.conf = cdb
        self.fs_ic = freeswitch_interconnect.freeswitch_ic(self.conf)
        self.tariff_type = "off_network_receive"
        self.msgid_db = MessageDB()

    def bill(self, to_number, from_number):
        try:
            if from_number == DASHBOARD_FROM_NUMBER:
                self.tariff_type = 'free_sms'
            tariff = billing.get_sms_cost(self.tariff_type,
                                          destination_number=to_number)
            username = subscriber.get_imsi_from_number(to_number)
            if username:
                reason = 'SMS from %s to %s (incoming_sms)' % (
                    from_number, username)
                old_balance = subscriber.get_account_balance(username)
                subscriber.subtract_credit(username, str(int(tariff)))
                events.create_sms_event(username, old_balance, tariff, reason,
                                        to_number, from_number=from_number)
        except Exception as e:
            logger.error("Endaga bill error:" + traceback.format_exc(e))

    def check_signed_params(self, jwt_data):
        """
        Decodes the params, makes sure they pass signature (i.e., are valid),
        and then checks that we haven't seen the msgid before. Raises a
        ValueError if errors, else returns True.

        TODO(matt): this particular method seems to be unused (not so the one
                    in federer_handlers.config.config).
        """
        s = itsdangerous.JSONWebSignatureSerializer(self.conf['bts_secret'])
        try:
            data = s.loads(jwt_data)
        except itsdangerous.BadSignature:
            logger.error("Bad jwt signature for request, ignoring.")
            raise ValueError("Bad signature")

        # make sure the msg hasn't been seen before, if so, discard it
        if "msgid" in data:
            if self.msgid_db.seen(str(data['msgid'])):
                logger.error("Endaga: Repeat msgid: %s" % (data['msgid'],))
                raise ValueError("Repeat msgid: %s" % (data['msgid'],))
        else:
            logger.error("Endaga: No message ID.")
            raise ValueError("No message ID.")

        return data
