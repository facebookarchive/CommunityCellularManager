"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import numbers
import re

from .currency import Currency, CURRENCIES, DEFAULT_CURRENCY  # noqa: F401

class Money(object):
    """A class that binds an amount to currency with the appropriate precision

    Args:
        amount: an amount of currency in traditional representation in
                floating or integer representation
        currency: the unit currency to bind to the amount. (default is USD)
        amount_raw: an amount of currency in precise integer representation.
                    To be used only when amount is not provided.
    """

    def __init__(self, amount=None, currency=DEFAULT_CURRENCY,
            amount_raw=None):
        if not (amount is None) ^ (amount_raw is None):
            raise ValueError("You must specify an amount or a raw amount")

        if not isinstance(currency, Currency):
            raise TypeError("You must specify a valid Currency")

        if amount is not None:
            if not isinstance(amount, numbers.Real):
                raise TypeError("Amount must be an integer or float")
            amount_raw = int(amount * 10**currency.precision)

        if not isinstance(amount_raw, numbers.Integral):
            raise TypeError("Amount must be an integer or float")

        self.amount_raw = amount_raw
        self.currency = currency


    @property
    def amount(self):
        """Formats the money as a floating point with the standard amount of
        precision."""
        precise_amount = self.amount_raw * 10**-self.currency.precision
        return round(precise_amount, self.currency.decimals)

    def __repr__(self):
        """Format money using the currency's format string.

        If amount is negative, the sign is moved to the front of the string

        >>> Money(-12)
        -$12.00
        >>> Money(123456.789)
        $123,456.79
        >>> Money(987654321, currency=CURRENCIES['IDR'])
        Rp 987654321
        """
        return self.money_str()


    def amount_str(self):
        """Format the amount using the currency's format string.
        >>> Money(-12).amount_str()
        -12.00
        >>> Money(123456.789).amount_str()
        123,456.79
        >>> Money(987654321, currency=CURRENCIES['IDR']).amount_str()
        987654321
        >>> Money(-987654321, currency=CURRENCIES['IDR']).amount_str()
        -987654321
        """
        string = self.currency.format_str.format(amount=self.amount,
                decimals=self.currency.decimals, symbol='', code='', name='',)
        return string.strip()

    def money_str(self, with_symbol=True):
        """ Format money using the currency's format string.

        If amount is negative, the sign is moved to the front of the string

        >>> Money(-12).money_str()
        -$12.00
        >>> Money(123456.789).money_str()
        $123,456.79
        >>> Money(987654321, currency=CURRENCIES['IDR']).money_str()
        Rp 987654321
        >>> Money(-987654321, currency=CURRENCIES['IDR']).money_str()
        Rp -987654321
        """
        # Strip the sign and move it to the front of the string
        #fails if any component cannot be converted to ascii -kurtis
        string = self.currency.format_str.format(
            amount=abs(self.amount),
            symbol=self.currency.symbol,
            code=self.currency.code,
            name=self.currency.name,
            decimals=self.currency.decimals)
        if self.amount_raw < 0:
            string, n = re.subn(r'\s', r' -', string, count=1)
            if n == 0:
                string = '-' + string
        return string


def humanize_credits(amount_raw, currency=DEFAULT_CURRENCY):
    """Given an integer credit amount, this will return a
    human friendly Money instance in the specified Currency.
    """
    return Money(amount_raw=amount_raw, currency=currency)

def parse_credits(numerical, currency=DEFAULT_CURRENCY):
    """Given a formatted numerical input (commas and decimals only)
    this will return a Money instance in the specified Currency.
    """
    if not isinstance(numerical, numbers.Real):
        # assume it's a string of some kind, if not we won't be able
        # to convert to float anyway
        numerical = re.sub(r',([0-9]{3})', r'\1', numerical)
    return Money(float(numerical), currency)
