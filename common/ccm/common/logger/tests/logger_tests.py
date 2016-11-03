"""Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

# Tests for the logger
#
# Usage:
#     nosetests tests.logger_tests

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from io import StringIO
import logging
import unittest

from ccm.common import logger


class LoggerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """ Send all log output to a string buffer that we can read. """
        cls.logbuf = StringIO()
        logger.DefaultLogger.update_handler(
            logging.StreamHandler(cls.logbuf),
            logging.INFO,
            True)
        logger.debug("directed logger output to buffer for logger tests")

    def _log_it(self, log_fn, message, **kwargs):
        pos = self.logbuf.tell()
        log_fn(message, tb_offset=1, **kwargs)
        buf = self.logbuf.getvalue()[:pos] + '*' + self.logbuf.getvalue()[pos:]
        print("buffer contents: " + buf)  # debugging
        self.logbuf.seek(pos)

    def test_logger_level(self):
        """ logger prints messages with level >= threshold. """
        # level < threshold
        self._log_it(logger.debug, "debug message is not logged")
        self.assertEqual(self.logbuf.read(), '')
        # level > threshold
        self._log_it(logger.warning, "warning message is logged")
        self.assertRegexpMatches(self.logbuf.read(),
                                 'warning message is logged$')
        # level == threshold
        self._log_it(logger.info, "info message is logged")
        self.assertRegexpMatches(self.logbuf.read(),
                                 'info message is logged$')

    def test_logger_annotation(self):
        """ logger adds correct annotations to message. """
        self._log_it(logger.info, "foo")
        # we don't look for a precise line number match
        expected = \
            "^\[INFO\] logger_tests.py:[0-9]+:test_logger_annotation: foo$"
        output = self.logbuf.read()
        # trim newline from end of output before comparing
        self.assertRegexpMatches(output[:-1], expected)

    def test_logger_kwargs(self):
        """ logger appends kwargs to message (sorted by key). """
        self._log_it(logger.info, "foo", a=1, b={str('x'): 5})
        expected = ": foo a=1 b={'x': 5}$"
        output = self.logbuf.read()
        # trim newline from end of output before comparing
        self.assertRegexpMatches(output[:-1], expected)

    def test_logger_traceback(self):
        """ logger can add additional stack frames to message. """
        self._log_it(logger.info, "bar", tb_limit=2)
        lines = len(self.logbuf.readlines())
        # expect 5 lines of output:
        # <message>
        # Traceback:
        # 3 stack frames
        self.assertEqual(lines, 5)

    def test_logging_module(self):
        """ logging with the standard module works just fine. """
        pos = self.logbuf.tell()
        logging.info("xyz")
        buf = self.logbuf.getvalue()[:pos] + '*' + self.logbuf.getvalue()[pos:]
        print("buffer contents: " + buf)  # debugging
        self.logbuf.seek(pos)
        # we don't look for a precise line number match
        expected = \
            "^\[INFO\] logger_tests.py:[0-9]+:test_logging_module: xyz$"
        output = self.logbuf.read()
        # trim newline from end of output before comparing
        self.assertRegexpMatches(output[:-1], expected)
