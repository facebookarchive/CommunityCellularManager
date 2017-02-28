""" Adds a number range to the database.

This is always a contiguous range. Skips numbers that are already present.

Examples:
    python manage.py add_number_block <start_num> <block_size> <country_id>
    python manage.py add_number_block 639360130000 1000 PH --kind <kind>

Use the '--kind' optional argument to specify the kind of number, e.g.,
number.telecom.permanent for a number that the cloud routes via a known
SIP gateway.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import argparse

from django.core.management.base import BaseCommand
from django.db import transaction

from endagaweb.models import Number

def _is_two_letter_string(value):
    val = str(value)
    if val.isalpha() and len(val) == 2:
        return val.upper()
    else:
        msg = "'%s' must be a two-letter alpha string"
        argparse.ArgumentTypeError(msg)

class Command(BaseCommand):
    help = 'Adds a contiguous number block to the DB.'


    def add_arguments(self, parser):
        parser.add_argument('start_num', type=int)
        parser.add_argument('block_size', type=int)
        parser.add_argument('country_id', type=_is_two_letter_string)
        parser.add_argument('--kind',
                            type=str,
                            default='local',
                            help='Kind of number, e.g., number.nexmo.monthly')

    def handle(self, *args, **options):
        start_num = options['start_num']
        block_size = options['block_size']
        country_id = options['country_id']
        kind = options['kind']

        for i in range(0, block_size):
            num = str(start_num + i)
            if Number.objects.filter(number=num).exists():
                print "Skipping %s, already in DB." % num
                continue
            n = Number(subscriber=None,
                       network=None,
                       number=str(num),
                       state="available",
                       country_id=country_id,
                       kind=kind)

            n.save()
            print "Added %s to DB." % (unicode(n),)
