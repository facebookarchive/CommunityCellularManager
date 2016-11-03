# -*- coding: utf-8 -*-

"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import unicode_literals

from django.db import models, migrations

import snowflake

from ccm.common import crdt


class Migration(migrations.Migration):
    def create_crdt_balances(apps, schema_editor):
        Subscriber = apps.get_model('endagaweb', "Subscriber")
        for s in Subscriber.objects.all().iterator():
            c = crdt.PNCounter()
            if s.old_balance < 0:
                print unicode(s)
                c.decrement(abs(int(s.old_balance)))
            else:
                c.increment(int(s.old_balance))
            s.crdt_balance = c.serialize()
            s.save()

    dependencies = [
        ('endagaweb', '0001_add_new_field'),
    ]

    operations = [
        migrations.RunPython(create_crdt_balances),
    ]
