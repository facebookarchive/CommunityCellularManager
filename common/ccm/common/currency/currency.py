"""Pretty money utilities here.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""


class Currency(object):
    """A Currency is container for attributes about a particular currency.

    Args:
        code: the ISO 4217 three character currency code
        name: the name of the currency unit
        symbol: the sign of the currency unit
        decimals: the number of decimal places the currency can represent
        precision: the number of decimals places of precision to keep
        format_str: a replacement field for formatting money of this currency
            using strings (symbol, code, name), ints (decimals) and floats (amount)
    """

    def __init__(self, code="", name="", symbol=u"", decimals=2, precision=0,
                    format_str=""):
        self.code = code
        self.name = name
        self.symbol = symbol
        self.decimals = decimals
        self.precision = precision
        self.format_str = format_str

    def __repr__(self):
        return self.code

CURRENCIES = {}

# Millicents USD
CURRENCIES['USD'] = Currency(code="USD", name="US Dollars", symbol=u"$",
        decimals=2, precision=5, format_str="{symbol}{amount:,.{decimals}f}")
# Rupiah IDR
CURRENCIES['IDR'] = Currency(code="IDR", name="Indonesian Rupiah", symbol=u"Rp",
        decimals=0, precision=0, format_str="{symbol} {amount:.0f}")
# Philippine Peso
# actual symbol is u"\u20B1" -kurtis
CURRENCIES['PHP'] = Currency(code="PHP", name="Philippine Peso", symbol=u"Php",
        decimals=2, precision=5, format_str="{symbol}{amount:,.{decimals}f}")

DEFAULT_CURRENCY = CURRENCIES['USD']
