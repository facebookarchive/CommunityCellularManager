"""
Helper methods for dealing with notifications

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from django.conf import settings
import django.utils.timezone
from django.template.loader import render_to_string

from endagaweb.celery import app as celery_app

def bts_up(bts):
    """ Checks if a BTS has come back from being offline, and sends
    notifications as appropriate.
    """
    if bts.status != 'active':
        # The BTS is back online! Great.
        data = {
            'bts_uuid_short': bts.uuid[:6],
            'bts_uuid': bts.uuid,
            'bts_nickname': bts.nickname,
        }
        if bts.nickname:
            email_subj = ("Alert: BTS %s (%s...) is online"
                            % (bts.nickname, bts.uuid[:6]))
        else:
            email_subj = "Alert: BTS %s online" % (bts.uuid)
        email_msg = render_to_string("internal/bts_up_email.html", data)
        sms_msg = render_to_string("internal/bts_up_sms.html", data)

        for email in bts.network.notify_emails.split(','):
            if len(email):
                params = (email_subj, email_msg,
                    settings.TEMPLATE_CONSTANTS['SUPPORT_EMAIL'], [email])
                celery_app.send_task('endagaweb.tasks.async_email', params)

        # We blindly assume the SMS is <140 char
        for number in bts.network.notify_numbers.split(','):
            if len(number):
                params = (sms_msg, number)
                celery_app.send_task('endagaweb.tasks.sms_notification', params)
