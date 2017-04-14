#!/usr/bin/env python3
"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

# -*- encoding: utf8 -*-
#
# $Id: gsm0338.py 4390 2010-04-14 06:58:43Z rjones $
# $HeadURL: svn+ssh://svn/svn/trunk/api/eklib/gsm0338.py $
#
#
# Copyright 2009-2011 ekit.com Inc
#
"""Python Character Mapping Codec generated from 'GSM0338.TXT' with
gencodec.py.
"""

# Ref: http://mail.python.org/pipermail/python-list/2002-October/167271.html

import codecs

### Codec APIs

class CharCodec(codecs.Codec):
    # Can't work - extension table is the suck.

    def encode(self, input, errors='strict'):
        return codecs.charmap_encode(input, errors, encoding_map)

    def decode(self, input, errors='strict'):
        return codecs.charmap_decode(input, errors, decoding_map)


class Codec(codecs.Codec):
    def encode(self, input, errors='strict'):
        result = []
        for n, c in enumerate(input):
            try:
                value = encoding_map[ord(c)]
                if value > 255:
                    result.append(value >> 8)
                result.append(value & 0xff)
            except KeyError:
                try:
                    extra = extra_encoding_map[ord(c)]
                    result.extend([0x001b, extra])
                except KeyError:
                    if errors == 'strict':
                        raise UnicodeEncodeError('GSM-0338', input, n, n + 1,
                                                 'character not in map')
                    elif errors == 'replace':
                        result.append(0x3f)  # ?
                    elif errors == 'ignore':
                        pass
                    else:
                        raise UnicodeError("unknown error handling")
        return ''.join([chr(x) for x in result])

    def decode(self, input, errors='strict'):
        result = []
        index = 0
        while index < len(input):
            c = input[index]
            index += 1
            if c == '\x1b':
                if index < len(input):
                    c = input[index]
                    index += 1
                    # try looking up the escaped encoding map but revert
                    # to the normal encoding map give up if the input is
                    # crap (the correct behavior in at least one case)
                    oc = ord(c)
                    if oc in extra_decoding_map:
                        result.append(extra_decoding_map[oc])
                    elif oc in decoding_map:
                        result.append(decoding_map[oc])
                    else:
                        raise ValueError('invalid escape code 0x%02x' % oc)
                elif errors == 'replace':
                    result.append(ord('?'))
                elif errors == 'ignore':
                    pass
                else:
                    raise ValueError('truncated data')
            else:
                try:
                    result.append(decoding_map[ord(c)])
                except KeyError:
                    # error handling: unassigned byte, must be > 0x7f
                    raise UnicodeDecodeError('GSM-0338', input, index, index + 1,
                                             'ordinal not in range(128)')
        try:
            return "".join([chr(x) for x in result]), len(result)
        except Exception as e:
            print("err", result)
            raise e

class StreamWriter(Codec, codecs.StreamWriter):
    pass


class StreamReader(Codec, codecs.StreamReader):
    pass


### encodings module API

def getregentry():
    return (Codec().encode, Codec().decode, StreamReader, StreamWriter)

### Decoding Map

extra_decoding_map = {0x000A: 0x000a,  # LINE FEED/PAGE BREAK
                      0x0014: 0x005e,  # CARET
                      0x001b: 0x00a0,  # ESCAPE TO EXTENSION TABLE 2
                                       # (or displayed as NBSP, see note above)
                      0x0028: 0x007B,  # LEFT BRACE
                      0x0029: 0x007D,  # RIGHT BRACE
                      0x002F: 0x005C,  # BACK SLASH
                      0x003C: 0x005B,  # LEFT SQUARE BRACKET
                      0x003D: 0x007E,  # TILDE
                      0x003E: 0x005D,  # RIGHT SQUARE BRACKET
                      0x0040: 0x007C,  # PIPE
                      0x0065: 0x20AC}  # EURO

decoding_map = {0x0000: 0x0040,  # COMMERCIAL AT
                0x0001: 0x00a3,  # POUND SIGN
                0x0002: 0x0024,  # DOLLAR SIGN
                0x0003: 0x00a5,  # YEN SIGN
                0x0004: 0x00e8,  # LATIN SMALL LETTER E WITH GRAVE
                0x0005: 0x00e9,  # LATIN SMALL LETTER E WITH ACUTE
                0x0006: 0x00f9,  # LATIN SMALL LETTER U WITH GRAVE
                0x0007: 0x00ec,  # LATIN SMALL LETTER I WITH GRAVE
                0x0008: 0x00f2,  # LATIN SMALL LETTER O WITH GRAVE
                0x0009: 0x00e7,  # LATIN SMALL LETTER C WITH CEDILLA
                0x000A: 0x000a,  # LINE FEED
                0x000b: 0x00d8,  # LATIN CAPITAL LETTER O WITH STROKE
                0x000c: 0x00f8,  # LATIN SMALL LETTER O WITH STROKE
                0x000D: 0x000d,  # CARRIAGE RETURN
                0x000e: 0x00c5,  # LATIN CAPITAL LETTER A WITH RING ABOVE
                0x000f: 0x00e5,  # LATIN SMALL LETTER A WITH RING ABOVE
                0x0010: 0x0394,  # GREEK CAPITAL LETTER DELTA
                0x0011: 0x005f,  # LOW LINE
                0x0012: 0x03a6,  # GREEK CAPITAL LETTER PHI
                0x0013: 0x0393,  # GREEK CAPITAL LETTER GAMMA
                0x0014: 0x039b,  # GREEK CAPITAL LETTER LAMDA
                0x0015: 0x03a9,  # GREEK CAPITAL LETTER OMEGA
                0x0016: 0x03a0,  # GREEK CAPITAL LETTER PI
                0x0017: 0x03a8,  # GREEK CAPITAL LETTER PSI
                0x0018: 0x03a3,  # GREEK CAPITAL LETTER SIGMA
                0x0019: 0x0398,  # GREEK CAPITAL LETTER THETA
                0x001a: 0x039e,  # GREEK CAPITAL LETTER XI
                # <rj> removed to allow correct encoding of NBSP
                # ('\x1b\x1b' rather than '\x1b')
                # 0x001b: 0x00a0,  # ESCAPE TO EXTENSION TABLE
                # (or displayed as NBSP, see note above)
                0x001c: 0x00c6,  # LATIN CAPITAL LETTER AE
                0x001d: 0x00e6,  # LATIN SMALL LETTER AE
                0x001e: 0x00df,  # LATIN SMALL LETTER SHARP S (German)
                0x001f: 0x00c9,  # LATIN CAPITAL LETTER E WITH ACUTE
                0x0020: 0x0020,  # SPACE
                0x0021: 0x0021,  # EXCLAMATION MARK
                0x0022: 0x0022,  # QUOTATION MARK
                0x0023: 0x0023,  # NUMBER SIGN
                0x0024: 0x00a4,  # CURRENCY SIGN
                0x0025: 0x0025,  # PERCENT SIGN
                0x0026: 0x0026,  # AMPERSAND
                0x0027: 0x0027,  # APOSTROPHE
                0x0028: 0x0028,  # LEFT PARENTHESIS
                0x0029: 0x0029,  # RIGHT PARENTHESIS
                0x002A: 0x002A,  # ASTERISK
                0x002B: 0x002B,  # PLUS SIGN
                0x002C: 0x002C,  # COMMA
                0x002D: 0x002D,  # HYPHEN-MINUS
                0x002E: 0x002E,  # FULL STOP
                0x002F: 0x002F,  # SOLIDUS
                0x0030: 0x0030,  # DIGIT ZERO
                0x0031: 0x0031,  # DIGIT ONE
                0x0032: 0x0032,  # DIGIT TWO
                0x0033: 0x0033,  # DIGIT THREE
                0x0034: 0x0034,  # DIGIT FOUR
                0x0035: 0x0035,  # DIGIT FIVE
                0x0036: 0x0036,  # DIGIT SIX
                0x0037: 0x0037,  # DIGIT SEVEN
                0x0038: 0x0038,  # DIGIT EIGHT
                0x0039: 0x0039,  # DIGIT NINE
                0x003A: 0x003A,  # COLON
                0x003B: 0x003B,  # SEMICOLON
                0x003C: 0x003C,  # LESS-THAN SIGN
                0x003D: 0x003D,  # EQUALS SIGN
                0x003E: 0x003E,  # GREATER-THAN SIGN
                0x003F: 0x003F,  # QUESTION MARK
                0x0040: 0x00a1,  # INVERTED EXCLAMATION MARK
                0x0041: 0x0041,  # LATIN CAPITAL LETTER A
                0x0042: 0x0042,  # LATIN CAPITAL LETTER B
                0x0043: 0x0043,  # LATIN CAPITAL LETTER C
                0x0044: 0x0044,  # LATIN CAPITAL LETTER D
                0x0045: 0x0045,  # LATIN CAPITAL LETTER E
                0x0046: 0x0046,  # LATIN CAPITAL LETTER F
                0x0047: 0x0047,  # LATIN CAPITAL LETTER G
                0x0048: 0x0048,  # LATIN CAPITAL LETTER H
                0x0049: 0x0049,  # LATIN CAPITAL LETTER I
                0x004A: 0x004A,  # LATIN CAPITAL LETTER J
                0x004B: 0x004B,  # LATIN CAPITAL LETTER K
                0x004C: 0x004C,  # LATIN CAPITAL LETTER L
                0x004D: 0x004D,  # LATIN CAPITAL LETTER M
                0x004E: 0x004E,  # LATIN CAPITAL LETTER N
                0x004F: 0x004F,  # LATIN CAPITAL LETTER O
                0x0050: 0x0050,  # LATIN CAPITAL LETTER P
                0x0051: 0x0051,  # LATIN CAPITAL LETTER Q
                0x0052: 0x0052,  # LATIN CAPITAL LETTER R
                0x0053: 0x0053,  # LATIN CAPITAL LETTER S
                0x0054: 0x0054,  # LATIN CAPITAL LETTER T
                0x0055: 0x0055,  # LATIN CAPITAL LETTER U
                0x0056: 0x0056,  # LATIN CAPITAL LETTER V
                0x0057: 0x0057,  # LATIN CAPITAL LETTER W
                0x0058: 0x0058,  # LATIN CAPITAL LETTER X
                0x0059: 0x0059,  # LATIN CAPITAL LETTER Y
                0x005A: 0x005A,  # LATIN CAPITAL LETTER Z
                0x005b: 0x00c4,  # LATIN CAPITAL LETTER A WITH DIAERESIS
                0x005c: 0x00d6,  # LATIN CAPITAL LETTER O WITH DIAERESIS
                0x005d: 0x00d1,  # LATIN CAPITAL LETTER N WITH TILDE
                0x005e: 0x00dc,  # LATIN CAPITAL LETTER U WITH DIAERESIS
                0x005f: 0x00a7,  # SECTION SIGN
                0x0060: 0x00bf,  # INVERTED QUESTION MARK
                0x0061: 0x0061,  # LATIN SMALL LETTER A
                0x0062: 0x0062,  # LATIN SMALL LETTER B
                0x0063: 0x0063,  # LATIN SMALL LETTER C
                0x0064: 0x0064,  # LATIN SMALL LETTER D
                0x0065: 0x0065,  # LATIN SMALL LETTER E
                0x0066: 0x0066,  # LATIN SMALL LETTER F
                0x0067: 0x0067,  # LATIN SMALL LETTER G
                0x0068: 0x0068,  # LATIN SMALL LETTER H
                0x0069: 0x0069,  # LATIN SMALL LETTER I
                0x006A: 0x006A,  # LATIN SMALL LETTER J
                0x006B: 0x006B,  # LATIN SMALL LETTER K
                0x006C: 0x006C,  # LATIN SMALL LETTER L
                0x006D: 0x006D,  # LATIN SMALL LETTER M
                0x006E: 0x006E,  # LATIN SMALL LETTER N
                0x006F: 0x006F,  # LATIN SMALL LETTER O
                0x0070: 0x0070,  # LATIN SMALL LETTER P
                0x0071: 0x0071,  # LATIN SMALL LETTER Q
                0x0072: 0x0072,  # LATIN SMALL LETTER R
                0x0073: 0x0073,  # LATIN SMALL LETTER S
                0x0074: 0x0074,  # LATIN SMALL LETTER T
                0x0075: 0x0075,  # LATIN SMALL LETTER U
                0x0076: 0x0076,  # LATIN SMALL LETTER V
                0x0077: 0x0077,  # LATIN SMALL LETTER W
                0x0078: 0x0078,  # LATIN SMALL LETTER X
                0x0079: 0x0079,  # LATIN SMALL LETTER Y
                0x007A: 0x007A,  # LATIN SMALL LETTER Z
                0x007b: 0x00e4,  # LATIN SMALL LETTER A WITH DIAERESIS
                0x007c: 0x00f6,  # LATIN SMALL LETTER O WITH DIAERESIS
                0x007d: 0x00f1,  # LATIN SMALL LETTER N WITH TILDE
                0x007e: 0x00fc,  # LATIN SMALL LETTER U WITH DIAERESIS
                0x007f: 0x00e0,  # LATIN SMALL LETTER A WITH GRAVE
                0x1b0a: 0x000c,  # FORM FEED
                0x1b14: 0x005e,  # CIRCUMFLEX ACCENT
                0x1b28: 0x007b,  # LEFT CURLY BRACKET
                0x1b29: 0x007d,  # RIGHT CURLY BRACKET
                0x1b2f: 0x005c,  # REVERSE SOLIDUS
                0x1b3c: 0x005b,  # LEFT SQUARE BRACKET
                0x1b3d: 0x007e,  # TILDE
                0x1b3e: 0x005d,  # RIGHT SQUARE BRACKET
                0x1b40: 0x007c,  # VERTICAL LINE
                0x1b65: 0x20ac}  # EURO SIGN

### Encoding Map

encoding_map = codecs.make_encoding_map(decoding_map)
extra_encoding_map = codecs.make_encoding_map(extra_decoding_map)

if __name__ == '__main__':
    import string
    c = Codec()
    def test(s):
        r = c.decode(c.encode(s))[0]
        if r != s:
            print('in %r != out %r' % (s, r))
    test(str(string.letters))
    test('\u20ac')
    test('\xa0')
    try:
        test('av\u20ad')
    except Exception as e:
        print(repr('av\u20ad'), 'raised', e)
    try:
        c.decode(u'caf\u00E9'.encode('utf8'))
    except Exception as e:
        print(repr(u'caf\u00E9'), 'raised', e)


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
