"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

'''Implements  a basic serial interface for fetching SMS PDUs from an
Ericcson T39 phone.

'''

import serial
from .pdu import SMS_SUBMIT


class T39(object):
    def __init__(self, file="/dev/tty.T39-SerialPort1-1"):
        self.file = file

        self.ser = serial.Serial(file, 115200)
        self.pdu = None

        for s in ('ATZ', 'AT+CPMS="ME","ME","ME"', 'AT+CNMI=3,3,2,0,0'):
            self.ser.write("%s\r" % s)

        while True:
            d = self.ser.readline()
            print(d)
            if d.startswith("OK"):
                break

    def fetch(self):
        s = self.ser.readline()
        self.pdu = SMS_SUBMIT.fromPDU(s)
        return self.pdu

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
