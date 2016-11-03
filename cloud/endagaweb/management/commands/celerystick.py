"""
Enforces a single global celerybeat instance.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import os
import syslog
import time
import uuid

from django.core.management.base import BaseCommand
import envoy

from endagaweb.models import Lock


class Command(BaseCommand):
    """A custom management command."""

    help = 'controls whether celerybeat runs on this instance'

    def handle(self, *args, **options):
        """
        Always try to grab the celerybeat lock, and if you get it start
        celerybeat. If not, stop any instances of celerybeat.

        Every instance of this script has a unique ID stored in memory for the
        duration of the process. If the process dies, it'll get a new UUID.
        While it's down, another process may pick up the lock and start its own
        celerybeat instance.

        We assume there is one instance of this script and one instance of
        celerybeat (both running inside supervisor) on each machine in the
        cluster.
        """
        my_id = str(uuid.uuid4())
        environment = os.getenv("CELERY_DEFAULT_QUEUE", "none")
        lock_name = '%s:celerybeat' % environment
        while True:
            if Lock.grab(lock_name, my_id, ttl=300):
                envoy.run('sudo supervisorctl start celerybeat')
                syslog.syslog("I have the lock: %s -> %s" % (lock_name, my_id))
            else:
                syslog.syslog("Can't grab lock: %s -> %s" % (lock_name, my_id))
                envoy.run('sudo supervisorctl stop celerybeat')
            time.sleep(240)
