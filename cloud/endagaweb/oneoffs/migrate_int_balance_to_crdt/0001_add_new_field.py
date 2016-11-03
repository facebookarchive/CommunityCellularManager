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

class Migration(migrations.Migration):
    dependencies = [
        ('endagaweb', 'REPLACE_ME_WITH_DEPENDENCY'),
    ]

    operations = [
        migrations.RenameField(
            model_name='subscriber',
            old_name='balance',
            new_name='old_balance',
        ),
        migrations.AddField(
            model_name='subscriber',
            name='crdt_balance',
            field=models.TextField(default=b'{}'),
        ),

    ]
