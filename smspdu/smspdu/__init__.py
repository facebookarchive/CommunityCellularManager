#!/usr/bin/env python3
"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

'''SMS PDU encoding and decoding, including GSM-0338 character set.

Overview
--------

This library handles SMS-DELIVER and SMS-SUBMIT format PDUs, and includes
full support for all data formats, flags and headers, and round-trips from
PDU to object and back again.

It also includes convenience APIs for constructing new PDUs from text or
data.

This library is very mature - it's been in production use for many years
before the 1.0 release was made. It's also, as far as I'm aware, the most
complete SMS PDU encoding and decoding library available.

The T39 functionality has been copied from the previous PyPI package with
the same name as this library to provide some continuity. It is untested.


PDU Interface
-------------

Typical usage will involve the SMS_SUBMIT and SMS_DELIVER .fromPDU(),
.toPDU() and .create() methods:

>>> from smspdu import SMS_SUBMIT
>>> pdu = SMS_SUBMIT.create('sender', 'recipient', 'hello, world')
>>> pdu.toPDU()
'010010D0F2F2380D4F97DD7400000CE8329BFD6681EE6F399B0C'
>>> pdu = smspdu.SMS_SUBMIT.fromPDU(_, 'sender')
>>> pdu.user_data
u'hello, world'


Command-line Usage
------------------

To decode a PDU on the command-line (using python2.7+), use::

  % python -m smspdu 010010D0F2F2380D4F97DD7400000CE8329BFD6681EE6F399B0C

  010010D0F2F2380D4F97DD7400000CE8329BFD6681EE6F399B0C
  tp_mti = 1 (SMS-SUBMIT)
  sender = unknown
  tp_rd = 0
  tp_vpf = 0
  tp_vp = None
  tp_rp = 0
  tp_udhi = 0
  tp_srr = 0
  tp_mr = 0
  tp_al = 16
  tp_toa = d0 (Alphanumeric; Unknown)
  (recipient) address = 'recipient'
  tp_pid = 0x00 (Normal Case)
  tp_dcs = 0x00 (Immedate Display, GSM-0338 Default Alphabet)
  tp_udl = 12
  tp_ud = '\\xe82\\x9b\\xfdf\\x81\\xeeo9\\x9b\\x0c'
  datestamp = 11062712173200
  user_data = u'hello, world'
  user_data_headers = []

The first line re-displays the PDU with the various sections colourised.

Users of versions of Python 2.6 will need to run "python -m smspdu.pdu".


SMS Text - Handling the Awesomeness of GSM 0338
------------------------------------------------

First the basics; encoding some text:

>>> from smspdu import gsm0338
>>> c = gsm0338()
>>> gsm_message = c.encode(u'test message')

And decoding that message:

>>> from smspdu import gsm0338
>>> c = gsm0338()
>>> c.decode(gsm_message)
u'test message'

The library also provides some functions for making text SMS-happy:

:func:`gsm0338_safe`
  A simplistic function which just replaces any characters in the unicode
  input. You should probably use :func:`attempt_encoding` instead since it
  tries to make the message appear the same.
:func:`attempt_encoding`
  Attempt to encode the supplied text for SMS transmission in a single
  message. This will alter the message to replace accents and typography
  where necessary to reduce the per-character septet count.
:func:`remove_accent`
  Used by :func:`attempt_encoding` to remove all accents from characters in
  the supplied text.
:func:`remove_typography`
  Used by :func:`attempt_encoding` to replaced typograpically-correct
  punctuation with simplified GSM-0338 characters.
:func:`decode_ascii_safe`
  Removes all non-printable, non-ASCII codes in the string.
:func:`smpp_to_sms_data_coding`
  Attempt to convert the SMPP data coding scheme (SMPP v34) to a useful
  SMS PDU (GSM 03.38) data coding scheme.

Version History (in Brief)
--------------------------

- 1.0 the initial release based on mature internal ekit.com code

----
This code is copyright 2011 eKit.com Inc (http://www.ekit.com/)
See the end of the source file for the license of use.

'''

__version__ = '1.1'

from .pdu import (SMS_SUBMIT, SMS_DELIVER, attempt_encoding,
            smpp_to_sms_data_coding, remove_accent, remove_typography,
                decode_ascii_safe)
from .gsm0338 import Codec as gsm0338



def gsm0338_safe(message):
    '''Make the given unicode string gsm0338-safe by replacing out any
    characters not present in the above.
    '''
    c = gsm0338()
    gsm_message = c.encode(message, 'replace')
    return c.decode(gsm_message)[0]


# Copyright (c) 2011 eKit.com Inc (http://www.ekit.com/)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
