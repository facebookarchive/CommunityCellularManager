#!/usr/bin/env python3
"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
"""Code for handling GSM 03.38/03.40 encoded SMSs.

This library allows for encoding and decoding SMS as TPDUs described in the
spec.

Based on the information from "Mobile Messaging Technologies and Services"
second edition by Gwenael Le Bodic, published by Wiley.

See http://www.dreamfabric.com/sms/ for a description which lacks some of
the detail of the book.
"""

import re
import time
import unicodedata
from . import gsm0338

SMS_TYPES = 'SMS-DELIVER SMS-SUBMIT SMS-STATUS-REPORT RESERVED'.split()


class PDUDecodeError(ValueError):
    pass


class UnexpectedPDUTypeError(PDUDecodeError):
    pass


class TruncatedPDUError(PDUDecodeError):
    pass


class PDUData(list):

    def int(self):
        return int(self.bytes(1), 16)

    def byte(self):
        return self.bytes(1)

    def bytes(self, num):
        try:
            return ''.join([self.pop(0) + self.pop(0) for i in range(int(num))])
        except IndexError:
            raise TruncatedPDUError('PDU is truncated')

    def octets(self, num=None):
        if num is not None:
            buf = self.bytes(num)
        else:
            buf = self.bytes(len(self) / 2)
        return ''.join([chr(int(c1 + c2, 16))
                       for c1, c2 in zip(buf[::2], buf[1::2])])


class SMS_GENERIC(object):
    def isData(self):
        '''Determine whether this PDU contains binary data.

        If True then .user_data is a str() otherwise it'll be unicode().
        '''
        if self.tp_dcs in (0, 8):
            return False
        elif self.tp_dcs & 0xF0 in (0xC0, 0xD0, 0xE0):
            return False
        return True

    def concatInfo(self):
        '''Extract the message concatenation information for this message.

        Return a dict with {'ref', 'count', 'seq', 'size'} keys or None.
        '''
        for header, val in self.user_data_headers:
            if header == 0:
                ref, count, seq = val
                return dict(size=8, ref=val[0], count=val[1], seq=val[2])
            elif header == 8:
                return dict(size=16, ref=(val[0] << 8) + val[1],
                            count=val[2], seq=val[3])

    @staticmethod
    def parseAddress(tpdu):
        '''Parse the TP-Address-Length, TP-Type-Of-Address and TP-Address
        from the start of the given TPDU and return the TOA, address and
        remaining TPDU.
        '''
        pl = tpdu.int()
        toa = tpdu.int()
        # XXX todo parse this
        if 0 and toa not in (0x91, 0x81):
            raise ValueError('expected toa of 81/91, not 0x%02x' % toa)
        address = tpdu.octets(pl / 2 + pl % 2)
        if (toa & 0x70) == 0x50:
            # GSM-coded address - decode to ASCII and strip any crap
            address = unpack7bit(address, 0)
            c = gsm0338.Codec()
            address = decode_ascii_safe(c.decode(address, 'replace')[0], False)
            # address = address.encode('ascii')

            # some phones put bits in the lower nybble of the TOA when
            # sending alphanumeric addresses; this is wrong wrong wrongedy
            # wrong "for Type-of-number = 101 bits 3,2,1,0 are reserved and
            # shall be transmitted as 0000" from the spec.
            toa &= 0xF0
        else:
            address = unpackPhoneNumber(address)
        return pl, toa, address

    def encodeAddress(self):
        data = []

        # in both cases, Address-Length (in semi-octets) then Type-of-Address
        data.append('%02X' % self.tp_al)
        data.append('%02X' % self.tp_toa)

        # followed by the Address-Value data.
        if self.tp_toa & 0xF0 == 0xD0:
            # alphanumeric, special case
            l, packed = pack7bit(self.tp_address)
            # trailing null byte isn't appreciated in addresses
            if packed[-1] == '\x00':
                packed = packed[:-1]
        else:
            # phone number, actual digits
            packed = packPhoneNumber(self.tp_address)
            if self.tp_al > len(self.tp_address):
                packed = '\x00' + packed

        # Address-Value data
        data.extend(['%02X' % ord(c) for c in packed])
        return ''.join(data)

    @staticmethod
    def determineAddress(address):
        '''Determine the TP-Address-Length, TP-Type-of-Address and
        TP-(Originating|Destination)-Address values for the supplied
        address string.
        '''
        if re.match('^\d+$', address):
            # phone number
            # Type-of-Address == 91         (international number)
            tp_al = len(address)
            tp_toa = 0x91
            packed = packPhoneNumber(address)
        else:
            # Type-of-Address == D0         (alphanumeric)
            c = gsm0338.Codec()
            l, packed = pack7bit(c.encode(address, 'replace'))
            tp_al = len(packed) * 2
            tp_toa = 0xD0
        return tp_al, tp_toa, packed

    @staticmethod
    def parseUD(tp_dcs, tp_ud, tp_udhi, tp_udl):
        '''Parse user data (ie. the message) out of the tp_ud data
        string.
        '''
        # pull out user-data headers if any
        if tp_udhi:
            data, headerlen, user_data_headers = SMS_GENERIC.parseUDH(tp_ud)
        else:
            data = tp_ud
            headerlen = 0
            user_data_headers = []

        # GSM 03.38, section 4
        if (tp_dcs & 0xc0) == 0:
            if tp_dcs & 0x20:
                raise PDUDecodeError('compressed data not supported: '
                                     'tp_dcs 0x%02x (%s)'
                                     % (tp_dcs, describe_tp_dcs(tp_dcs)))
                data = decompress_user_data(data)
            try:
                charset = {0x00: '7bit', 0x04: '8bit',
                           0x08: 'utf-16'}[tp_dcs & 0x0c]
            except KeyError:
                raise PDUDecodeError('invalid DCS : tp_dcs 0x%02x '
                                     '(specifies unknown charset)' % tp_dcs)
        elif (tp_dcs & 0xf0) in (0xc0, 0xd0):
            # MWI, Default Alphabet
            charset = '7bit'
        elif (tp_dcs & 0xf0) == 0xe0:
            # MWI, USC2
            charset = 'utf-16'
        elif (tp_dcs & 0xf0) == 0xf0:
            charset = {0x00: '7bit', 0x04: '8bit'}[tp_dcs & 0x04]
        else:
            raise PDUDecodeError('unhandled tp_dcs 0x%02x (%s)' % (tp_dcs,
                                 describe_tp_dcs(tp_dcs)))

        # figure the number of characters (or octets, for data) that are
        # expected based on the tp_udl minus however many header octets
        # we've seen
        actual_udl = tp_udl - headerlen

        # now decode the user data
        if charset == '7bit':  # basic 7 bit coding - 03.38 S6.2.1
            data = unpack7bit(data, headerlen)
            c = gsm0338.Codec()
            user_data, length = c.decode(data)
            user_data = user_data[:actual_udl]
        elif charset == '8bit':  # 8 bit coding is "user defined". S6.2.2
            user_data = unpack8bit(data)
            user_data = user_data[:actual_udl]
        elif charset == 'utf-16':  # UTF-16 aka UCS2, S6.2.3
            try:
                user_data = unpackUCS2(data)
                user_data = user_data[:actual_udl]
            except UnicodeDecodeError as e:
                raise PDUDecodeError('PDU corrupted(%s) : %s' % (e, data))
        else:
            raise PDUDecodeError('tp_dcs of 0x%02x (%s), charset %s' % (tp_dcs,
                                 describe_tp_dcs(tp_dcs), charset))

        return user_data, user_data_headers

    @staticmethod
    def parseUDH(user_data):
        '''Parse user data headers out of the start of the given TP-User-Data
        string.
        '''
        headers = []
        headerlen = 0

        headerlen = ord(user_data[0])
        header = user_data[1:headerlen + 1]
        user_data = user_data[headerlen + 1:]
        while header:
            ie = ord(header[0])
            ielen = ord(header[1])
            val = header[2:2 + ielen]
            headers.append((ie, [ord(x) for x in val]))
            header = header[2 + ielen:]

        return user_data, headerlen, headers

    @staticmethod
    def determineUD(user_data, tp_dcs, user_data_headers):
        '''Figure the TP-User-Data content and generate the PDU
        parameters tp_udhi, tp_dcs, tp_udl and tp_ud.
        '''
        if user_data_headers:
            tp_udhi = 1

            h = ''
            for ie, val in user_data_headers:
                h += chr(ie) + chr(len(val)) + ''.join(map(chr, val))
            tp_ud = chr(len(h)) + h

        else:
            tp_udhi = 0
            tp_ud = ''

        top_nybble = tp_dcs & 0xF0

        if top_nybble == 0xC0:
            # Message Waiting Indication Group: Discard Message GSM
            codec = 'gsm'
        elif top_nybble == 0xD0:
            # Message Waiting Indication Group: Store Message GSM
            codec = 'gsm'
        elif top_nybble == 0xE0:
            # Message Waiting Indication Group: Store Message UCS2
            codec = 'ucs2'
        elif top_nybble == 0xF0:
            # Data coding / message class
            codec = ['gsm', None][(tp_dcs & 0x04) >> 2]
        else:
            # either General Data Coding indication (0x0X .. 0x3X)
            #     or Automatic Deletion (0x4X .. 0xbX)
            # (note that the book says Automatic Deletion but the GSM spec
            # says Reserved ... either way I'll just pass through)
            try:
                codec = ['gsm', None, 'ucs2'][(tp_dcs & 0x0C) >> 2]
            except IndexError:
                raise ValueError('bad tp_dcs value (reserved alphabet)')

        if codec == 'gsm':
            # GSM-0338 default alphabet
            c = gsm0338.Codec()

            # play it safe and force encoding with replace
            encoded = c.encode(user_data, 'replace')

            # TP-User-Data 7bit packed GSM-0338 encoded funky sh!t
            l, user_data = pack7bit(encoded, len(tp_ud))
            tp_udl = l + len(tp_ud)

        elif codec == 'ucs2':
            # UCS2
            user_data = str(user_data.encode('utf_16_be', 'replace'))
            length = len(user_data)
            if length > 140:
                raise ValueError('UCS-2 message too long (%d>140 chars)' %
                                 length)
            tp_udl = len(user_data) + len(tp_ud)

        else:
            # 8-bit data
            tp_udl = len(user_data) + len(tp_ud)

        tp_ud += user_data

        return tp_udhi, tp_dcs, tp_udl, tp_ud

    def dump(self):
        l = []
        l.append('tp_mti = %s (%s)' % (self.tp_mti, self.type))
        if self.type == 'SMS-SUBMIT':
            l.append('sender = %s' % self.sender)
            l.append('tp_rd = %s' % self.tp_rd)
            l.append('tp_vpf = %s' % self.tp_vpf)
            l.append('tp_vp = %s' % self.tp_vp)
            l.append('tp_rp = %s' % self.tp_rp)
            l.append('tp_udhi = %s' % self.tp_udhi)
            l.append('tp_srr = %s' % self.tp_srr)
            l.append('tp_mr = %s' % self.tp_mr)
        elif self.type == 'SMS-DELIVER':
            l.append('recipient = %s' % self.recipient)
            l.append('tp_mms = %s' % self.tp_mms)
            l.append('tp_rp = %s' % self.tp_rp)
            l.append('tp_udhi = %s' % self.tp_udhi)
            l.append('tp_sri = %s' % self.tp_sri)
            l.append('tp_scts = %s' % self.tp_scts)
        else:
            raise NotImplementedError

        l.append('tp_al = %s' % self.tp_al)
        toa = ('%02x (%s; %s)' %
               (self.tp_toa,
                {
                    0x00: 'Unknown',
                    0x10: 'International number',
                    0x20: 'National number',
                    0x30: 'Network specific number',
                    0x40: 'Subscriber number',
                    0x50: 'Alphanumeric',
                    0x60: 'Abbreviated number',
                }.get(self.tp_toa & 0x70, 'Reserved'),
                {
                    0x0: 'Unknown',
                    0x1: 'ISDN/telephone numbering plan (E.164/E.163)',
                    0x3: 'Data numbering plan (X.121)',
                    0x4: 'Telex numbering plan',
                    0x8: 'National numbering plan',
                    0x9: 'Private numbering plan',
                    0xA: 'ERMES numbering plan (ETSI DE/PS 3 01-3)',
                }.get(self.tp_toa & 0xF, 'Reserved')))
        l.append('tp_toa = %s' % toa)
        l.append('(%s) address = %r' %
                 ({'SMS-SUBMIT':
                   'recipient', 'SMS-DELIVER': 'sender'}[self.type],
                  self.tp_address))

        l.append('tp_pid = 0x%02x (%s)' % (self.tp_pid,
                 describe_tp_pid(self.tp_mti, self.tp_pid)))
        l.append('tp_dcs = 0x%02x (%s)' % (self.tp_dcs,
                 describe_tp_dcs(self.tp_dcs)))

        l.append('tp_udl = %s' % self.tp_udl)
        l.append('tp_ud = %r' % self.tp_ud)
        l.append('datestamp = %s' %
                 time.strftime('%y%m%d%H%M%S00', time.localtime(self.datestamp)))
        l.append('user_data = %r' % self.user_data)
        l.append('user_data_headers = %s' % self.user_data_headers)
        return '\n'.join(l)


class SMS_DELIVER(SMS_GENERIC):
    '''Encapsulate an SMS-DELIVER message.
    '''

    type = 'SMS-DELIVER'

    def __init__(self, tp_mti, tp_mms, tp_rp, tp_udhi, tp_sri, tp_al, tp_toa,
                 tp_oa, tp_pid, tp_dcs, tp_scts, tp_udl, tp_ud, recipient,
                 datestamp=None, user_data=None, user_data_headers=None):
        self.tp_mti = tp_mti
        self.tp_mms = tp_mms
        self.tp_rp = tp_rp
        self.tp_udhi = tp_udhi
        self.tp_sri = tp_sri
        self.tp_al = tp_al
        self.tp_toa = tp_toa
        self.sender = self.tp_address = self.tp_oa = tp_oa
        self.tp_pid = tp_pid
        self.tp_dcs = tp_dcs
        self.tp_scts = tp_scts
        self.tp_udl = tp_udl
        self.tp_ud = tp_ud
        self.recipient = recipient
        self.datestamp = datestamp or time.time()
        self.user_data = user_data
        self.user_data_headers = user_data_headers

    @classmethod
    def create(cls, sender, recipient, user_data, datestamp=None,
               tp_sri=0, tp_mms=0, tp_rp=0, tp_pid=0, tp_dcs=None,
               tp_scts=None, user_data_headers=None):
        '''Create an SMS message using the supplied information.

        "sender" and "recipient" are string MSISDNs
        "user_data" is a unicode string for text messages or
                    a plain string if data
        "datestamp" is a float UTC timestamp
        "tp_pid" is the TP-Protocol-ID
        "tp_dcs" is the TP-Data-Coding-Scheme (if not supplied we'll guess)
        "tp_sri" is the TP-Status-Report-Indication
        "tp_rp" is the TP-ReplyPath indicator
        "tp_mms" is the TP-More-Messages-to-Send indicator
        "user_data_headers" gives additional user_data headers to
                send (eg. concatenation information)
        '''
        if user_data_headers is None:
            user_data_headers = []
        if tp_dcs is None:
            tp_dcs = guess_dcs(user_data)
        tp_udhi, tp_dcs, tp_udl, tp_ud = cls.determineUD(user_data, tp_dcs,
                                                         user_data_headers)

        tp_mti = 0      # TP-Messages-Type-Indicator (SMS-DELIVER)

        # TP-Service-Centre-Time-Stamp
        if tp_scts:
            if not datestamp:
                # XXX datestamp ignores / loses timestamp
                datestamp = time.mktime(time.strptime('20' + tp_scts[:12],
                                        '%Y%m%d%H%M%S'))
        else:
            if datestamp is None:
                datestamp = time.time()
            tp_scts = time.strftime('%y%m%d%H%M%S00', time.localtime(datestamp))

        # determine TP-Address-Length and TP-Type-of-Address
        tp_al, tp_toa, tp_oa = cls.determineAddress(sender)

        return cls(tp_mti, tp_mms, tp_rp, tp_udhi, tp_sri, tp_al, tp_toa,
                   sender, tp_pid, tp_dcs, tp_scts, tp_udl, tp_ud, recipient,
                   datestamp, user_data, user_data_headers)

    @classmethod
    def fromPDU(cls, tpdu, recipient, datestamp=None):
        '''Create a SMS object from a PDU string (class method).

        "tpdu" is the GSM PDU *assumed to be from a Service Center (SC)*
        "recipient" has the recipient's MSISDN
        "datestamp" is the time the PDU was generated / received

        Note that this method ASSUMES THE TPDU IS FROM A SERVICE CENTER
        (SC) and not a handset (MS). This affects the intepreration of the
        Message-Type-Indicator.

        If the message is from a handset then SMS_SUBMIT.fromPDU should
        be used!
        '''
        tpdu = PDUData(tpdu)

        # Set instance attributes
        first = tpdu.int()
        tp_mti = first & 0x03  # message type
        if tp_mti != 0:
            raise UnexpectedPDUTypeError('TPDU is not of type '
                                         'SMS-DELIVER (is %s)'
                                         % SMS_TYPES[tp_mti])

        # pull the rest of the bits out of the header byte
        tp_rp = (first & 0x80) >> 7     # reply-path
        tp_udhi = (first & 0x40) >> 6   # user-data header indicator
        tp_sri = (first & 0x20) >> 5    # status report indicator
        tp_mms = (first & 0x04) >> 2    # more messages to send

        # TP-Address-Length, TP-Type-Of-Address and TP-Address
        tp_al, tp_toa, tp_oa = cls.parseAddress(tpdu)

        # TP-Protocol-ID
        tp_pid = tpdu.int()

        # TP-Data-Coding-Scheme
        tp_dcs = tpdu.int()

        # TP-SCTS time stamp
        tp_scts = unpack_date(tpdu.octets(7))
        if not datestamp:
            # XXX datestamp ignores / loses timestamp
            datestamp = time.mktime(time.strptime('20' + tp_scts[:12],
                                                  '%Y%m%d%H%M%S'))

        # TP-User-Data(-Length) and headers
        tp_udl = tpdu.int()
        tp_ud = tpdu.octets()
        user_data, user_data_headers = cls.parseUD(tp_dcs, tp_ud, tp_udhi,
                                                   tp_udl)

        return cls(tp_mti, tp_mms, tp_rp, tp_udhi, tp_sri, tp_al, tp_toa,
                   tp_oa, tp_pid, tp_dcs, tp_scts, tp_udl, tp_ud, recipient,
                   datestamp, user_data, user_data_headers)

    def toPDU(self, coloured=False):
        """Turn this SMS object into a PDU in hex string format.

        "coloured" should only ever be used in debugging as it inserts
        ANSI colouring escape codes into the PDU string to colour the
        various parts of the PDU.
        """
        tpdu = []
        if coloured:
            tpdu.append('\x1b[0m\x1b[47;31m')     # on teal

        first = 0x00                            # TP-Message-Type-Indicator
        if self.tp_mms:
            first |= 0x04           # TP-More-Messages-To-Send
        if self.tp_sri:
            first |= 0x20           # TP-Status-Report-Indicator
        if self.tp_udhi:
            first |= 0x40          # TP-User-Data-Header-Indicator
        if self.tp_rp:
            first |= 0x80            # TP-Reply-Path
        tpdu.append('%02X' % first)

        if coloured:
            tpdu.append('\x1b[47;32m')     # on green

        # TP-Originating-Address
        tpdu.append(self.encodeAddress())

        if coloured:
            tpdu.append('\x1b[47;33m')     # on gold

        # TP-Protocol-ID
        # use specified protocol id
        tpdu.append('%02X' % self.tp_pid)

        if coloured:
            tpdu.append('\x1b[47;34m')     # on blue

        # TP-Data-Coding-Scheme
        tpdu.append('%02X' % self.tp_dcs)

        if coloured:
            tpdu.append('\x1b[47;35m')     # on purple

        # TP-Service-Centre-Time-Stamp
        tp_scts = pack_date(self.tp_scts)
        tpdu.append(''.join(['%02X' % ord(c) for c in tp_scts]))

        if coloured:
            tpdu.append('\x1b[47;91m')     # bright red

        # TP-User-Data-Length and TP-User-Data (and headers)
        tpdu.append('%02X' % self.tp_udl)

        if coloured:
            tp_ud = self.tp_ud
            if self.tp_udhi:
                tpdu.append('\x1b[47;34m')     # bright blue
                n = ord(tp_ud[0]) + 1
                h = tp_ud[:n]
                tp_ud = tp_ud[n:]
                tpdu.append(''.join(['%02X' % ord(c) for c in h]))

            tpdu.append('\x1b[47;30m')     # black
            tpdu.append(''.join(['%02X' % ord(c) for c in tp_ud]))
        else:
            tpdu.append(''.join(['%02X' % ord(c) for c in self.tp_ud]))

        if coloured:
            tpdu.append('\x1b[01;0m')
        return ''.join(tpdu)

    # alias
    toDeliverPDU = toPDU


class SMS_SUBMIT(SMS_GENERIC):
    '''Encapsulate an SMS-SUBMIT message.
    '''
    type = 'SMS-SUBMIT'

    def __init__(self, tp_mti, tp_rd, tp_vpf, tp_rp, tp_udhi, tp_srr,
                 tp_mr, tp_al, tp_toa, tp_da, tp_pid, tp_dcs, tp_vp, tp_udl,
                 tp_ud, sender, datestamp=None, user_data=None,
                 user_data_headers=None):
        self.tp_mti = tp_mti
        self.tp_rd = tp_rd
        self.tp_vpf = tp_vpf
        self.tp_rp = tp_rp
        self.tp_udhi = tp_udhi
        self.tp_srr = tp_srr
        self.tp_mr = tp_mr
        self.tp_al = tp_al
        self.tp_toa = tp_toa
        self.recipient = self.tp_address = self.tp_da = tp_da
        self.tp_pid = tp_pid
        self.tp_dcs = tp_dcs
        self.tp_vp = tp_vp
        self.tp_udl = tp_udl
        self.tp_ud = tp_ud
        self.sender = sender
        self.datestamp = datestamp or time.time()
        self.user_data = user_data
        self.user_data_headers = user_data_headers

    @classmethod
    def create(cls, sender, recipient, user_data, datestamp=None,
               tp_pid=0, tp_dcs=None, tp_rd=0, tp_rp=0, tp_vpf=0,
               tp_vp=None, tp_srr=0, tp_mr=0, user_data_headers=None):
        '''Create an SMS message using the supplied information.

        "sender" and "recipient" are string MSISDNs
        "user_data" is a unicode string for text messages or
                    a plain string if data
        "datestamp" is a float timestamp
        "tp_pid" is the TP-Protocol-ID
        "tp_dcs" is the TP-Data-Coding-Scheme (if not supplied we'll guess)
        "tp_rd"  is TP-Reject-Duplicates (default: dupes OK)
        "tp_rp"  is TP-ReplyPath (not set)
        "tp_vpf" is the TP-Validity-Period-Format
        "tp_vp" is the TP-Validity-Period formatted according to
                the VPF and supplied as described below.
        "tp_srr" is TP-Status-Report-Request (default: no report requested)
        "tp_mr" is the TP-Message-Reference, an integer
        "user_data_headers" gives additional user_data headers
                to send (eg. concatenation information)

        tp_vp should be passed values as appropriate for the tp_vpf:

        ====== =======================================================
        tp_vpf tp_vp
        ====== =======================================================
        0      No tp_vp should be passed; it will be ignored.
        1      A sequence of 7 octets (ints) containing the extended
               validity period data.
        2      A single octet (int) containing the relative validity
               period data.
        3      A string containing the absolite validity data:
               "YYMMDDhhmmss*ZZ" where "*" is either "+" or "-"
               and ZZ is the timezone offset in *quarters of an hour*
               (so +1 hour is "+04")
        ====== =======================================================
        '''
        if tp_dcs is None:
            tp_dcs = guess_dcs(user_data)
        if user_data_headers is None:
            user_data_headers = []
        tp_udhi, tp_dcs, tp_udl, tp_ud = cls.determineUD(user_data, tp_dcs,
                                                         user_data_headers)

        tp_mti = 0      # TP-Messages-Type-Indicator (SMS-DELIVER)

        if datestamp is None:
            datestamp = time.time()

        # determine TP-Address-Length and TP-Type-of-Address
        tp_al, tp_toa, tp_da = cls.determineAddress(recipient)

        return cls(tp_mti, tp_rd, tp_vpf, tp_rp, tp_udhi, tp_srr, tp_mr,
                   tp_al, tp_toa, recipient, tp_pid, tp_dcs, tp_vp, tp_udl,
                   tp_ud, sender, datestamp, user_data, user_data_headers)

    @classmethod
    def fromPDU(cls, tpdu, sender, datestamp=None):
        '''Create a SMS object from a PDU string (class method).

        "tpdu" is the GSM PDU
        "sender" has the sender's MSISDN
        "datestamp" is the time the PDU was generated / received
        '''
        tpdu = PDUData(tpdu)

        datestamp = datestamp or time.time()

        # Parse the PDU

        # Set instance attributes
        first = tpdu.int()
        tp_mti = first & 0x03  # message type
        if tp_mti != 1:
            raise UnexpectedPDUTypeError('TPDU is not of type '
                                         'SMS-SUBMIT (is %s)'
                                         % SMS_TYPES[tp_mti])

        tp_rp = (first & 0x80) >> 7       # TP-Reply-Path
        tp_udhi = (first & 0x40) >> 6     # TP-User-Data-Header-Indicator
        tp_srr = (first & 0x20) >> 5      # TP-Status-Report-Request
        tp_vpf = (first & 0x18) >> 3      # TP-Validity-Period-Format
        tp_rd = (first & 0x04) >> 2       # TP-Reject-Duplicates

        # SMS-SUBMIT TP-Message-Reference
        tp_mr = tpdu.int()

        # TP-Address-Length, TP-Type-Of-Address and TP-Address
        tp_al, tp_toa, tp_da = cls.parseAddress(tpdu)

        # TP-Protocol-ID
        tp_pid = tpdu.int()

        # TP-Data-Coding-Scheme
        tp_dcs = tpdu.int()

        # optional TP-Validity-Period
        tp_vp = None
        if tp_vpf == 2:
            tp_vp = int(tpdu.byte(), 16)
        elif tp_vpf == 1:
            tp_vp = list(map(ord, tpdu.octets(7)))
        elif tp_vpf == 3:
            tp_vp = unpackPhoneNumber(tpdu.octets(7))

        # TP-User-Data(-Length) and headers
        tp_udl = tpdu.int()
        tp_ud = tpdu.octets()
        user_data, user_data_headers = cls.parseUD(tp_dcs, tp_ud, tp_udhi,
                                                   tp_udl)

        return cls(tp_mti, tp_rd, tp_vpf, tp_rp, tp_udhi, tp_srr,
                   tp_mr, tp_al, tp_toa, tp_da, tp_pid, tp_dcs, tp_vp, tp_udl,
                   tp_ud, sender, datestamp, user_data, user_data_headers)

    def toPDU(self, coloured=False):
        """Turn this SMS object into a PDU in hex string format.
        """
        tpdu = []
        if coloured:
            tpdu.append('\x1b[0m\x1b[47;31m')     # teal

        first = 0x01                            # TP-Message-Type-Indicator
        if self.tp_rd:
            first |= 0x04            # TP-Reject-Duplicates
        if self.tp_vpf:
            first |= (self.tp_vpf << 3)  # TP-Validity-Period-Format
        if self.tp_srr:
            first |= 0x20           # TP-Status-Report-Request
        if self.tp_udhi:
            first |= 0x40          # TP-User-Data-Header-Indicator
        if self.tp_rp:
            first |= 0x80            # TP-Reply-Path
        tpdu.append('%02X' % first)

        if coloured:
            tpdu.append('\x1b[47;32m')     # green

        # TP-Message-Reference
        tpdu.append('%02X' % self.tp_mr)

        if coloured:
            tpdu.append('\x1b[47;33m')     # gold

        # TP-Destination-Address
        tpdu.append(self.encodeAddress())

        if coloured:
            tpdu.append('\x1b[47;34m')     # blue

        # TP-Protocol-ID
        # use specified protocol id
        tpdu.append('%02X' % self.tp_pid)

        if coloured:
            tpdu.append('\x1b[47;35m')     # purple

        # TP-Data-Coding-Scheme
        tpdu.append('%02X' % self.tp_dcs)

        if coloured:
            tpdu.append('\x1b[47;36m')     # cyan

        # TP-Validity-Period
        if self.tp_vpf == 2:
            tpdu.append('%02X' % self.tp_vp)
        elif self.tp_vpf == 1:
            tpdu.append(''.join(['%02X' % n for n in self.tp_vp]))
        elif self.tp_vpf == 3:
            # absolute datestamp
            tp_vp = packPhoneNumber(self.tp_vp)
            tpdu.append(''.join(['%02X' % ord(c) for c in tp_vp]))

        if coloured:
            tpdu.append('\x1b[47;91m')     # bright red

        # TP-User-Data-Length and TP-User-Data (and headers)
        tpdu.append('%02X' % self.tp_udl)

        if coloured:
            tp_ud = self.tp_ud
            if self.tp_udhi:
                tpdu.append('\x1b[47;34m')     # bright blue
                n = ord(tp_ud[0]) + 1
                h = tp_ud[:n]
                tp_ud = tp_ud[n:]
                tpdu.append(''.join(['%02X' % ord(c) for c in h]))

            tpdu.append('\x1b[47;30m')     # black
            tpdu.append(''.join(['%02X' % ord(c) for c in tp_ud]))
        else:
            tpdu.append(''.join(['%02X' % ord(c) for c in self.tp_ud]))

        if coloured:
            tpdu.append('\x1b[0m')

        return ''.join(tpdu)

    def toDeliverPDU(self, coloured=False):
        """Turn this SMS object into an SMS_DELIVER PDU in hex string
        format.

        We have to fudge a few things:

        ============================= ======================================
        SMS-DELIVER                   SMS-SUBMIT
        ----------------------------- --------------------------------------
        TP-More-Messages-To-Send      not present; no analogue in SMS-SUBMIT
        TP-Status-Report-Indicator    use TP-Status-Report-Request
        TP-Service-Centre-Time-Stamp  use datestamp from creation
        ============================= ======================================

        And of course we lose the TP-Validity-Period information.
        """
        tp_al, tp_toa, tp_oa = self.determineAddress(self.sender)
        tp_scts = time.strftime('%y%m%d%H%M%S00',
                                time.localtime(self.datestamp))
        return SMS_DELIVER(
            0,                  # tp_mti: SMS-DELIVER
            0,                  # tp_mms: no analog in SMS-SUBMIT
            self.tp_rp,         # copy
            self.tp_udhi,       # copy
            self.tp_srr,        # tp_sri: copy SMS-SUBMIT tp_srr
            tp_al,              # calculate OA from SMS-SUBMIT sender
            tp_toa,             # "
            self.sender,        # SMS-SUBMIT sender passed in unpacked
            self.tp_pid,        # copy
            self.tp_dcs,        # copy
            tp_scts,            # datestamp from SMS-SUBMIT reception
            self.tp_udl,        # copy
            self.tp_ud,         # copy
            self.recipient,     # copy
            datestamp=self.datestamp,
            user_data=self.user_data,
            user_data_headers=self.user_data_headers
        ).toPDU(coloured=coloured)


PID_TELEMATIC_DEVICES = {
    0: 'Implicit',  # - device type is specific to this SC, or can be
                    # concluded on the basis of the address
    1: 'Telex (or teletex reduced to telex format)',
    2: 'Group 3 telefax',
    3: 'Group 4 telefax',
    4: 'Voice telephone (i.e. conversion to speech)',
    5: 'ERMES (European Radio Messaging System)',
    6: 'National Paging system (known to the SC)',
    7: 'Videotex (T.100/T.101)',
    8: 'Teletex, carrier unspecified',
    9: 'Teletex, in PSPDN',
    10: 'Teletex, in CSPDN',
    11: 'Teletex, in analog PSTN',
    12: 'Teletex, in digital ISDN',
    13: 'UCI (Universal Computer Interface, ETSI DE/PS 3 01-3)',
    14: 'Reserved',
    15: 'Reserved',
    16: 'A message handling facility (known to the SC)',
    17: 'Any public X.400-based message handling system',
    18: 'Internet Electronic Mail',
    19: 'Reserved',
    20: 'Reserved',
    21: 'Reserved',
    22: 'Reserved',
    23: 'Reserved',
    31: 'A GSM mobile station',  # The SC converts the SM from the received
                                 # TP-Data-Coding-Scheme to any data coding
                                 # scheme supported by that MS (e.g. the
                                 # default).
}
# 11000..11110 values specific to each SC, usage based on mutual agreement
# between the SME and the SC (7 combinations available for each SC)

def describe_tp_pid(tp_mti, tp_pid):
    top = tp_pid & 0xc0
    if top == 0:
        bottom = tp_pid & 0x1f
        if tp_pid & 0x20:
            device = PID_TELEMATIC_DEVICES.get(bottom)
            if not device:
                device = 'SC-specific usage (%d)' % bottom
            return 'Telematic Interworking: source is %s' % device
        if tp_mti == 0x01:  # SMS-SUBMIT
            if bottom:
                return 'SME-to-SME (0x%02x)' % bottom
            else:
                return 'Normal Case'
        elif tp_mti == 0x00:  # SMS-DELIVER
            if bottom:
                return 'SME-to-SME: SM-AL protocol is 0x%02x' % bottom
            else:
                return 'Normal Case'
        else:
            return '(PDU not SMS-SUBMIT or SMS-DELIVER)'
    elif top == 0x40:
        bottom = tp_pid & 0x3f
        if not bottom:
            return 'Short Message Type 0 (ack & discard on receipt)'
        elif top < 8:
            return 'Replace Short Message Type %d' % bottom
        elif bottom == 0x1f:
            return 'Return Call Message'
        elif bottom == 0x3d:
            return 'ME Data Download'
        elif bottom == 0x3e:
            return 'ME De-Personalization Short Message'
        elif bottom == 0x3f:
            return 'SIM Data Download'
        return 'Reserved'

    # SC-specific use
    return 'SC-Specific Usage'


def describe_tp_dcs(tp_dcs):
    if tp_dcs & 0xC0 == 0x40:
        return 'Reserved Coding Group'

    if tp_dcs & 0xF0 in (0xC0, 0xD0, 0xE0):
        coding = 'GSM-0338 Default Alphabet'
        if tp_dcs & 0xF0 == 0xC0:
            group = 'MWI/Discard'
        elif tp_dcs & 0xF0 == 0xD0:
            group = 'MWI/Store'
        elif tp_dcs & 0xF0 == 0xE0:
            group = 'MWI/Store'
            coding = 'UCS2'
        message_class = {
            0x00: 'Voicemail Message Waiting',
            0x01: 'Fax Message Waiting',
            0x02: 'Electronic Mail Message Waiting',
            0x03: 'Other Message Waiting',
        }[tp_dcs & 0x03]
        if tp_dcs & 0x08:
            message_class += ', Set Indication Active'
        else:
            message_class += ', Set Indication Inctive'
    else:
        message_class = {
            0x00: 'Immedate Display',
            0x01: 'ME-Specific',
            0x02: 'SIM-Specific',
            0x03: 'Terminal-Specific',
        }[tp_dcs & 0x03]
        coding = {
            0x0: 'GSM-0338 Default Alphabet',
            0x4: '8-bit Data',
            0x8: 'UCS2',
            0xC: 'Reserved',
        }[tp_dcs & 0xC]
        if tp_dcs & 0xC0 == 0x40:
            group = 'Automatic Deletion'
        elif tp_dcs & 0xF0 == 0xF0:
            group = 'Data Coding/Message Class'
        else:
            group = ''
    if (tp_dcs & 0xc0) == 0 and tp_dcs & 0x20:
        coding = 'compressed ' + coding

    return ', '.join([_f for _f in [group, message_class, coding] if _f])


def guess_dcs(message):
    '''Given a plain-text message try to guess an appropriate DCS.
    '''
    # figure encoding and add TP-DCS, TP-UDL and TP-UD (enforcing the 140
    # octet maximum length of TP-UD)
    c = gsm0338.Codec()
    try:
        # GSM-0338 (7-bit)
        length = len(c.encode(message))

        # TP-User-Data-Length -- number of septets (characters)
        if length > 160:
            raise ValueError('7-bit message too long (%d>160 chars)' %
                             length)

        return 0
    except UnicodeError:
        # UCS2 (well, UTF-16) big-endian
        length = len(message.encode('utf_16_be'))
        if length > 140:
            raise ValueError('UCS-2 message too long (%d>140 chars)' %
                             length)
        return 8


def generate_mwi_dcs(type, active, message):
    '''Given a MWI type, active flag and unicode message generate a DCS for
    an SMS PDU.

    Return the (possibly modified) message and the tp_dcs to use.
    '''
    dcs = dict(voicemail=0, fax=1, email=2, other=3)[type]

    if active == 'active':
        dcs |= 0x08

    if not message:
        return message, dcs | 0xC0

    message, x = attempt_encoding(message)
    try:
        gsm0338.Codec().encode(message)
        # code with GSM 0338
        return message, dcs | 0xD0
    except UnicodeError:
        # code with UCS2
        return message, dcs | 0xE0


def parse_udhi(data, debug=False):
    headers = {}
    headerlen = 0

    if debug:
        print("user-data", ' '.join([hex(ord(x)) for x in data]))
    headerlen = ord(data[0])
    if debug:
        print("header len", headerlen)
    header = data[1:headerlen + 1]
    if debug:
        print("header", ' '.join([hex(ord(x)) for x in header]))
    data = data[headerlen + 1:]
    while header:
        ie = ord(header[0])
        ielen = ord(header[1])
        ieval = header[2:2 + ielen]
        headers[ie] = ieval
        header = header[2 + ielen:]
    if debug:
        print("headers", headers)

    for ie, val in list(headers.items()):
        if ie == 0:
            headers[ie] = [ord(x) for x in val]    # reference, max, cnum
        elif ie == 8:
            headers[ie] = [
                (ord(val[0]) << 8) + ord(val[1]),  # reference
                ord(val[2]),                       # number of components
                ord(val[3]),                       # component sequence number
            ]

    return data, headerlen, headers


def unpack8bit(bytes):
    bytes = [ord(x) for x in bytes]
    return ''.join([chr(x) for x in bytes])


def unpackUCS2(buf):
    # XXX(omar) hocus pocus
    return buf.encode('latin1').decode('UTF-16-be')


def decompress_user_data(bytes):
    '''Decompress

    Input The Compressed Data Stream
    Step 1
        Interpret the Compression Header to determine the nature of the
        decompression to be performed.
        Note that it is the responsibility of higher software layers that use
        the decompression algorithms to handle appropriately the case where
        the nature of the decompression to be performed is not supported by a
        particular implementation.
    Step 2
        Initialize as defined by the CH the following components:
            1) Character Set Converter
            2) PunctuationProcessor
            3) KeywordProcessor
            4) UCS2Processor
            5) Character Group Processor
            6) HuffmanProcessor
    Step 3
        Interpret the Compression Footer to determine the total number of
        significant bits in the Compressed Data (CD). Set the total number of
        bits processed to zero.
    Step 4
        Read bits from the CD passing them to the Huffman decoder to generate
        the "current symbol". The bits should be read in the order bit 7 to
        bit 0 within each CD octet. CD octets are processed in the order 1
        to n.
    Step 5
        If the Keyword processor is not enabled, goto Step 6.
        If the "current symbol" is the Keyword symbol, read the bit sequence
        describing the keyword entry from the CD. Pass the keyword entry
        description to the Keyword processor for decoding and add the
        resulting sequence of characters representing the keyword to the
        output stream.
        Goto Step 9.
    Step 6
        If the Character Group processor is not enabled goto Step 7. If the
        "current symbol" is a Character Group Transition symbol, pass it to
        the Character Group processor so that the current group can be
        updated and goto Step 9.
        If the value of the "current symbol" is in the range 0 to 255
        (i.e. not a control symbol), pass the "current symbol" to the
        Character Group processor and set the new value of the "current
        symbol" to that returned by the Character Group processor.
    Step 7
        If the output stream is not UCS2 goto Step 8. If the "current symbol"
        is the New USC2 Row symbol, read the new "current UCS2 row octet"
        from the CD and goto Step 9.
        Pre-pend the "current UCS2 row octet" to the 8 bit value of the
        "current symbol" to produce a 16 bit UCS2 character.
    Step 8
        Add the "current symbol" to the output stream.
    Step 9
        Increment the total number of bits processed by the number of bits
        read from the CD in steps 4 to 8 above.
        If the total number of bits processed is less than the total number
        of significant bits in the CD goto Step 4.
    Step 10
        If the Punctuation Processor is enabled, use it to decode output
        stream produced by steps 3 to 9 above.
    Step 11
        If the Character set (UCS2 or otherwise) specified in the CH, is
        different from that required by higher level software layers, convert
        the output stream produced by step 10 above so that it is rendered
        in the Character set (UCS2 or otherwise) required by higher level
        software layers.
        Note that if characters in the stream cannot be converted, it is the
        responsibility of higher software layers that use the compression
        algorithms to detect this situation and take appropriate action.
    Output The decompressed original input stream
    '''
    bytes = bytearray(bytes)
    header = CompressionHeader(bytes)
    print(header)


class CompressionHeader:
    '''Parse the compression header from the byte stream, consuming its
    bytes as it goes.
    '''
    LANGUAGES = ['German', 'English', 'Italian', 'French', 'Spanish', 'Dutch',
                 'Swedish', 'Danish', 'Portuguese', 'Finnish', 'Norwegian',
                 'Greek', 'Turkish', 'Hungarian', 'Polish',
                 'Language unspecified']
    def __init__(self, bytes):
        octet = bytes.pop(0)
        self.compression_language_context = (octet & 0x78) >> 3
        self.punctuation_processing = bool(octet & 0x4)
        self.keyword_processing = bool(octet & 0x2)
        self.character_group_processing = bool(octet & 0x1)
        while octet & 0x80:
            octet = bytes.pop(0)

    def __str__(self):
        return '; '.join([
            'Language: %s' % self.LANGUAGES[self.compression_language_context],
            'Punctuation: %s' % self.punctuation_processing,
            'Keywords: %s' % self.keyword_processing,
            'Character Groups: %s' % self.character_group_processing,
        ])


def punctuate_user_data(bytes):
    '''Decompress the bytes as per 3GPP TS 23.042

    Input: "de-punctuated stream of characters to be punctuated,
    rendered in the character set used for compression.
    '''
    bytes = list(reversed(list(bytes)))

    # STEP 1: start at the start of the stream
    # STEP 2: determine attributes of the current character
    # - if the current character is the first character in the stream then
    #   convert to upper case and go to step 8
    # STEP 3: If the current character has the PU-IWS attribute and the
    # "previous character" attributes has the PU-UCW attribute, convert
    # the stored value of the "previous character" to upper case.
    # STEP 4: If the "previous character" attributes contain the PU-UCF
    # attribute, and the current character was not generated by Step 10 below,
    # convert the current character to upper case and clear the PU-UCF
    # attribute for the "previous character" attributes.
    # STEP 5: If the "previous character" was generated as a result of Step 10
    # and the current character contains the PU-NSI attribute goto Step 7.
    # STEP 6: Add the "previous character" value to the output stream.
    # STEP 7: If "previous character" attributes contain the PU-IWS attribute
    # and the current character has the PU-UCW attribute, add the PU-UCW
    # attribute to those of the "previous character". Otherwise clear any
    # PU-UCW attribute stored for the "previous character".
    # STEP 8: Set the value of the "previous character" to be that of the
    # current character.
    # STEP 9: If the attributes of the current character contain the PU-UCF
    # attribute set this attribute for the "previous character".
    # STEP 10: If the attributes of the current character contain the PU-WSF
    # attribute and the current character is not the last character in the
    # de-punctuated stream, insert the character containing the PU-IWS
    # attribute at the position following the current character in the
    # de-punctuated stream.
    # STEP 11: If the current character is not the last character in the
    # de-punctuated stream, read the next character from the stream, set the
    # current character to this value and goto Step 2.
    # STEP 12: Add the previous character to the output stream.
    # If the current character attributes do not contain the PU-UCF attribute
    # or the previous character value equals that of the character which has
    # the PU-LST attribute set, add the character which has the PU-LST
    # attribute set to the output stream.
    # ... PROFIT


# Of _course_ it's little endian. Mother f$ckers
_sevenBitMasksUnpack = (
    [(0x7F, 0), ],
    [(0xFE, 1), (0x00, 7)],
    [(0xFC, 2), (0x01, 6)],
    [(0xF8, 3), (0x03, 5)],
    [(0xF0, 4), (0x07, 4)],
    [(0xE0, 5), (0x0F, 3)],
    [(0xC0, 6), (0x1F, 2)],
    [(0x80, 7), (0x3F, 1)],
)


def unpack7bit(bytes, hl=0):
    """ Unpack a 7 bit ASCII string that's been packed into an 8 bit string
        Of course, it's &^$*&$ little endian.

        See http://www.dreamfabric.com/sms/hello.html for an example
    """
    bytes = [ord(x) for x in bytes]
    out = []
    if hl == 0:
        curOff = 0
    else:
        # I quote from section 9.2.3.24 of GSM 03.40:
        # If 7 bit data is used and the TP-UD-Header does not finish on
        # a septet boundary then fill bits are inserted after the last
        # Information Element Data octet up to the next septet boundary
        # so that there is an integral number of septets for the entire
        # TP-UD header. This is to ensure that the SM itself starts on
        # an septet boundary so that an earlier Phase mobile will be
        # capable of displaying the SM itself although the TP-UD Header
        # in the TP-UD field may not be understood. Please kill me now.
        curOff = (7 - ((8 * hl + 1) % 7)) % 7
    while bytes:
        masks = _sevenBitMasksUnpack[curOff]
        if len(masks) == 1:
            mask, shift = masks[0]
            out.append((bytes[0] & mask) >> shift)
        else:
            (mask0, shift0), (mask1, shift1) = masks
            if len(bytes) == 1:
                b = ((bytes[0] & mask0) >> shift0)
                if b:
                    out.append(b)
                break
            else:
                out.append(((bytes[0] & mask0) >> shift0) |
                           ((bytes[1] & mask1) << shift1))
                bytes = bytes[1:]
        curOff = (curOff + 7) % 8
    bytes = ''.join([chr(x) for x in out])
    return bytes


_sevenBitMasksPack = (
    # byte N        byte N+1
    (0x7f, 0x01),

)


def fmt_binary(n):
    bStr = ''
    while n > 0:
        bStr = str(n % 2) + bStr
        n = n >> 1
    return bStr.zfill(8)


def pack7bit(string, headerlen=0):
    """ Pack a string of 7-bit characters into an 8-bit using the funky 7bit
    septets transformation.

    Account for the header length (in octets): if the header doesn't finish
    on a septet boundary we need to pack it out (see unpack7bit for more
    info).

    Return the number of septets (even partial, so include the leading
    crap) and the packet string.

    See URL above for an example.
    """
    n = 0
    num_septets = len(string)

    # determine starting bit to output at
    if headerlen:
        # need to find the next multiple of 7 up from the current header
        # length
        cur = 8 * headerlen
        if cur % 7:
            n = 7 - (cur // 7) % 7
        num_septets = len(string) + 1

    # pack all those pesky septets into one big number
    bignum = 0
    for c in string:
        septet = ord(c)
        bignum |= septet << n
        n += 7

    # now grab octets from that big number, starting from the bottom
    m = 0
    l = []
    while n > 0:
        mask = 0xFF << m
        l.append((bignum & mask) >> m)
        m += 8
        n -= 8

    return num_septets, ''.join(map(chr, l))


def unpackPhoneNumber(bytes):
    "Turn 'decimal encoded semi-octets' number into normal text"
    bytes = nibbleswap(bytes)
    out = ['%02x' % (ord(b)) for b in bytes]
    return ''.join(out).rstrip('Ff')


def packPhoneNumber(bytes):
    "Turn a perfectly normal phone number into 'decimal encoded semi-octets'"
    if len(bytes) % 2:
        bytes += 'F'
    out = [chr(int(c1 + c2, 16))
           for c1, c2 in zip(bytes[::2], bytes[1::2])]
    return nibbleswap(''.join(out))


def pack_date(date):
    """Turn a string containing "YYMMDDhhmmss*ZZ" into 7 octets of packed
    data (for tp_scts, tp_vp and tp_dt).

    For convenience and backwards compatibility we also support
    "YYMMDDhhmmss00".

    Where "*" is either "+" or "-" and ZZ is the timezone offset in
    *quarters of an hour* (so +1 hour is "+04")
    """
    if len(date) == 14 and date[-2:] == '00':
        end = '00'
    elif date[-3] == '+':
        end = date[-2:]
    else:
        # negative TZ has the high (sign) bit set
        end = '%02x' % (int(date[-2:]) | 128)
    return packPhoneNumber(date[:12] + end)

def unpack_date(date):
    """Turn an absolute time representation value into a nice string
    containing "YYMMDDhhmmss*ZZ".

    For convenience and backwards compatibility we also support
    "YYMMDDhhmmss00".

    Where "*" is either "+" or "-" and ZZ is the timezone offset in
    *quarters of an hour* (so +1 hour is "+04")
    """
    date = unpackPhoneNumber(date)
    end = int(date[-2:], 16)
    if not end:
        end = '00'
    elif end & 128:
        end = '-%02d' % (end & 0x7f,)
    else:
        end = '+' + date[-2:]
    return date[:12] + end


def nibbleswap(bytes):
    # How much do I fucking hate SMS TPDU format?
    # nibbleswapping the output is the final indignation
    bytes = [ord(x) for x in bytes]
    bytes = [(b & 0xF0) >> 4 | (b & 0x0F) << 4 for b in bytes]
    bytes = ''.join([chr(x) for x in bytes])
    return bytes

SMPP_ISO_CHARSETS = {
    3: 'iso-8859-1',
    6: 'iso-8859-5',
    7: 'iso-8859-8',
}


def smpp_to_sms_data_coding(smpp_dcs, content):
    '''Attempt to convert the SMPP data coding scheme (SMPP v34) to a useful
    SMS PDU (GSM 03.38) data coding scheme.

    The top nybble of the data coding scheme is the same for both
    specifications; it's just the lower nybble that the fuckers couldn't
    agree on. Since the SMS PDU spec dictates what's actually transmitted
    to the handset it trumps the SMPP one.

    Fortunately for non-trivial messages (ie. top nybble != 0) the SMPP
    spec says "see the GSM spec" so we just pass those through.

    We currently cannot handle messages in JIS (0208 or 0212) or KS C 5601.
    '''
    top = smpp_dcs & 0xf0
    if top:
        return smpp_dcs, content
    bottom = smpp_dcs & 0xf

    # default alphabet or ASCII; pass on
    if bottom in (0, 1):
        return 0, content

    # raw binary - 0000 0100
    # note I've included "pictogram encoding" and "music codes" as "raw
    # data"
    if bottom == (2, 4, 9, 10):
        return 4, content

    # UCS2 - 0000 1000
    if bottom == 8:
        return 8, content

    # one of the ISO charsets (iso-8859-1, iso-8859-5, iso-8859-8) or just
    # give the hell up
    charset = SMPP_ISO_CHARSETS.get(bottom, 'ascii')
    content, b = attempt_encoding(content.decode(charset, 'ignore'))
    content = gsm0338.Codec().encode(content)
    return 0, content


def remove_accent(u):
    '''Code snarfed from
    http://stackoverflow.com/questions/517923/...
        ...what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
    '''
    nkfd_form = unicodedata.normalize('NFKD', u)
    return "".join([c for c in nkfd_form if not unicodedata.combining(c)])


def remove_typography(u):
    '''Replace typographical punctuation / quotation with plain ASCII
    marks.

    Also backtick "`" isn't in GSM so replace it with forward.

    Go with shorter, less-correct versions if the replacement versions push
    the text out too far.

    TODO A more complete list of possible substitutions is at
    http://www.cs.sfu.ca/~ggbaker/reference/characters/
    '''
    BEST = {u'\u201C': '"', u'\u201D': '"', u'\u2018': "'", u'\u2019': "'", u'\u2013': '-',
            u'\u00AB': '<<', u'\u00BB': '>>', u'\u2026': '...', u'\u2122': 'TM', '`': "'"}
    BETTER = dict(BEST)
    BETTER.update({u'\u00AB': '<', u'\u00BB': '>'})
    GOOD = dict(BETTER)
    GOOD.update({u'\u2026': '.'})

    # try the replacements
    for d in BEST, BETTER, GOOD:
        s = ''.join([d.get(c, c) for c in u])
        if len(s) < 160:
            break
    return s


def replace_gsm_doubles(u):
    '''Replace common characters that encode to double-width characters in
    GSM - this is a last-ditch effort to get a message to fit (presumably
    one that didn't originate from a handset)
    '''
    REPLACE = {'[': '(', ']': ')', '{': '(', '}': ')', '~': '-', '\\': '/',
               '\u20ac': 'E'}
    return ''.join([REPLACE.get(c, c) for c in u])


def attempt_encoding(u, limit=160):
    '''Given the input unicode string attempt to encode it for SMS delivery.

    This means taking some arbitrary input text and fitting it, encoded,
    within the 160 septet limit (overridable) of an SMS packet. Some
    characters in the input may not be encodable at all, some may encode to
    multiple characters in the SMS packet.

    The rules for handling the input text are:

    1. attempt to encode with GSM-0338,
    2. remove typographical characters (eg, curly quotes),
    3. attempt to represent without accents,
    4. attempt to replace common characters that encode to double-width
       characters, and
    5. give up and use UTF-16.

    Using UTF-16 is a last resort since it halves the message length.

    Returns two things: the potentially-translated and truncated string and
    the string containing any excess characters.
    '''
    # Attempt to encode with GSM-0338 + translations
    gsm = gsm0338.Codec()
    l = []
    e = []
    s = ''
    for c in u:
        # replace all control codes
        if ord(c) < 0x20 and c not in '\r\n':
            c = '?'
        try:
            t = gsm.encode(c)
        except UnicodeError:
            translated = remove_typography(c)
            translated = remove_accent(translated)
            if c == translated:
                # no translation possible; can't encode in GSM
                break
            c = translated
            try:
                t = gsm.encode(c)
            except UnicodeError:
                # translated but we still can't GSM encode
                break
        s += t
        if len(s) > limit:
            e.append(c)
        else:
            l.append(c)
    else:
        if e:
            # one last thing to try....
            s = ''.join(l) + ''.join(e)
            s = replace_gsm_doubles(s)
            if len(s) <= 160:
                return (s, '')
        return (''.join(l), ''.join(e))

    # encode using UTF-16
    l = []
    e = list(u)
    while e:
        c = e.pop(0)
        t = ''.join(l) + c
        if len(t.encode('utf16')) > 140:
            break
        l.append(c)
    return (''.join(l), ''.join(e))


def decode_ascii_safe(s, crlfok=True):
    '''Remove all non-printable, non-ASCII codes in the string.
    '''
    u = []
    for c in s:
        if ord(c) > 0x7e:
            # strip DEL and higher
            continue
        if (ord(c) < 0x20 and c not in '\r\n'):
            # strip control codes - and yes, I checked that messages with
            # these characters aren't actually GSM encoded. They're not.
            continue
        if not crlfok and c in '\r\n':
            # newlines just ain't OK in some situations
            continue
        u.append(c)
    return ''.join(u)


def dump(pdu):
    first = int(pdu[0:2], 16)
    tp_mti = first & 0x03  # message type
    if tp_mti == 1:
        p = SMS_SUBMIT.fromPDU(pdu, 'unknown')
        print()
        print(p.toPDU(1))
        print(p.dump())
    else:
        p = SMS_DELIVER.fromPDU(pdu, 'unknown')
        print()
        print(p.toPDU(1))
        print(p.dump())


if __name__ == '__main__':
    import sys
    dump(sys.argv[1])

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
