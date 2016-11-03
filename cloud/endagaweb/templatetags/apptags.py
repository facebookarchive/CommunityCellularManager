"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime

from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma
from django.template import Library
import pytz

from ccm.common.currency import humanize_credits, CURRENCIES


register = Library()


@register.simple_tag(takes_context=True)
def currency(context, amount, *args, **kwargs):
    if 'unit' in kwargs:
        currency = CURRENCIES[kwargs['unit']]
    else:
        currency = context['currency']

    money = humanize_credits(amount, currency)
    if 'amount_only' in kwargs and kwargs['amount_only']:
        return money.amount_str()
    return money


@register.filter
def duration(seconds):
    seconds = abs(seconds)
    if seconds < 60: # under a min
        return "%d seconds" % seconds
    elif seconds < 60*60: # under an hour
        return "%.0f minutes" % (seconds / 60.0,)
    elif seconds < 60*60*24*3: # under three days
        return "%.1f hours" % (seconds / (60.0*60.),)
    else: # more than three days
        return "%.1f days" % (seconds / (60.0*60*24*3),)


@register.filter
def timezone_offset(timezone):
    """Takes a tz name like 'US/Eastern' and returns 'US/Eastern - UTC-05:00'.

    Intended to be used by the timezone notification page fragment.  The pytz
    package should gracefully handle DST so the above will render 'US/Eastern -
    UTC-04:00' when DST is in effect.
    """
    if timezone == 'UTC':
        return 'UTC'
    now = datetime.datetime.now()
    try:
        seconds = pytz.timezone(timezone).utcoffset(now).total_seconds()
    except (pytz.NonExistentTimeError, pytz.AmbiguousTimeError):
        # If we're in the midst of a DST transition, add an hour and try again.
        now = now + datetime.timedelta(hours=1)
        seconds = pytz.timezone(timezone).utcoffset(now).total_seconds()
    sign = '+'
    if seconds < 0:
        # The minus sign is added automatically!
        sign = ''
    hours, remainder = divmod(seconds, 60*60)
    minutes, _ = divmod(remainder, 60)
    offset = '%02d:%02d' % (hours, minutes)
    display = '%s (UTC%s%s)' % (timezone, sign, offset)
    return display


@register.simple_tag
def tmpl_const(name):
    try:
        return settings.TEMPLATE_CONSTANTS.get(name, "")
    except AttributeError:
        return ""
