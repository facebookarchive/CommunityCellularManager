"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import json

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db import connection

from endagaweb.models import Number
from endagaweb.models import Transaction
from endagaweb.models import UserProfile


@login_required(login_url='/login/')
def numbers(request):
    user_profile = UserProfile.objects.get(user=request.user)
    connection.ops.date_trunc_sql('month', 'created')

    try:
        numbers = Number.objects.get(user=user_profile).order_by("-created")
    except Number.DoesNotExist:
        numbers = []

    resp = [n.created for n in numbers]
    return HttpResponse(json.dumps(resp), content_type="application/json")


@login_required(login_url='/login/')
def totals(request):
    user_profile = UserProfile.objects.get(user=request.user)
    resp = {}

    try:
        resp['sms.out'] = Transaction.objects.get(ledger=user_profile.ledger,
                                                  kind="sms.out.nexmo").count()
    except Transaction.DoesNotExist:
        resp['sms.out'] = 0

    try:
        resp['sms.in'] = Transaction.objects.get(ledger=user_profile.ledger,
                                                 kind="sms.in.nexmo").count()
    except Transaction.DoesNotExist:
        resp['sms.in'] = 0

    try:
        resp['numbers'] = Number.objects.get(user=user_profile).count()
    except Number.DoesNotExist:
        resp['numbers'] = 0

    return HttpResponse(json.dumps(resp), content_type="application/json")
