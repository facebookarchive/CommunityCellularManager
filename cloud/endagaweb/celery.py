"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import

from datetime import timedelta
import os

from celery import Celery
from celery.schedules import crontab

from django.conf import settings


assert 'DJANGO_SETTINGS_MODULE' in os.environ
app = Celery('endagaweb')
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


# Setup celerybeat.
app.conf.update(CELERYBEAT_SCHEDULE={
    'vacuum-subscribers-with-no-outbound-activity': {
        'task': 'endagaweb.tasks.vacuum_inactive_subscribers',
        # Run this at 15:00 UTC (10:00 PDT, 02:00 Papua time).
        'schedule': crontab(minute=0, hour=17),
    },'facebook-ods-checkin': {
        'task': 'endagaweb.tasks.facebook_ods_checkin',
        # Run this every minute
        'schedule': crontab(minute='*'),
    },'downtime-notify': {
        'task': 'endagaweb.tasks.downtime_notify',
        # Run this every timeout period
        'schedule': timedelta(seconds=settings.ENDAGA['BTS_INACTIVE_TIMEOUT_SECS']),
    },'usageevents_to_sftp': {
        'task': 'endagaweb.tasks.usageevents_to_sftp',
        # Run this at 15:00 UTC (10:00 PDT, 02:00 Papua time)
        'schedule': crontab(minute=0, hour=17),
    }
})
