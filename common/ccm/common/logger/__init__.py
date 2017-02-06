"""Endaga/CCM global loggers.

We create a standard logging.Logger object to be used by callers of the
logger() method. We also install a syslog handler on the root logger so
that all messages that are created using the logging module get sent to
syslog, even if they didn't originate from this module.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
from logging.handlers import SysLogHandler
from os import environ
from sys import stderr
from syslog import LOG_DEBUG, LOG_LOCAL0
import traceback


# add a 'notice' level, between WARNING (30)  and INFO (20)
_NOTICE = 25
logging.addLevelName("NOTICE", 25)


# export Formatter templates so they can be used elsewhere, e.g., Django
# logging configuration.
SIMPLE_FORMAT = "%(filename)s:%(lineno)d:%(funcName)s: %(message)s"
VERBOSE_FORMAT = "[%(levelname)s] " + SIMPLE_FORMAT


class DefaultLogger(object):
    """ Capture state of default logging config.

    The environment variable CCM_LOGGER_NAME can be used to set a specific
    logger name, e.g., endagaweb, that may be more appropriate in some cases.
    """
    _log = logging.getLogger(environ.get("CCM_LOGGER_NAME", __name__))
    # Add 'endaga:' as format prefix for compatibility with old format
    _log_formatter = logging.Formatter("endaga: " + SIMPLE_FORMAT)
    _log_verbose = logging.Formatter(VERBOSE_FORMAT)
    _log_handler = None

    @classmethod
    def log(cls, level, message, tb_offset=2, tb_limit=0):
        """ Add file/function/lineno info to log message. Optionally add a
        stack trace if the caller requests it, for use, say, in tracking down
        calls to deprecated code; tb_limit specifies how many additional stack
        frames the caller wishes to append to the message.

        The default tb_offset of 2 is appropriate for direct calls to this
        function: caller's stack frame is second on the stack (this function
        is first). When called from a module-level function the tb_offset of 4
        is necessary to skip over the two additional stack frames incurred by
        the top-level module function, e.g., debug(), and _handle_log_event().
        """
        assert tb_limit >= 0 and tb_offset >= 2
        # Logger.handle() method doesn't check log levels, so we have to do so
        # explicitly. That also saves us creating stack traces we don't need.
        if not cls._log.isEnabledFor(level):
            return

        tb = traceback.extract_stack(limit=(tb_offset + tb_limit))
        # discard the stack frames we don't care about (following offset)
        tb = tb[:-tb_offset + 1]
        if tb_limit:
            message = '\n'.join(
                [message, 'Traceback:'] +
                # Python 3 barfs on f without the funky '[:]' operator
                [("  %s:%d:%s: %s" % f[:]) for f in tb])
        (pathname, lineno, function, _) = tb[-1]

        # by using standard LogRecord fields we are compatible with direct
        # calls to the standard logging infrastructure (those that bypass
        # this module, e.g., in endagaweb).
        rec = cls._log.makeRecord(__name__, level, pathname, lineno,
                                  message, args=None, exc_info=None,
                                  func=function)
        cls._log.handle(rec)

    @staticmethod
    def _get_logging_level(level):
        """ Map a syslog level to a logging level. The logging module
        levels start from 10 (DEBUG) and increase by 10 for every level of
        of severity (INFO, WARNING, ERROR, CRITICAL). syslog starts at 0
        for the most severe messages (EMERGENCY) and increases by 1 for
        each lower level of messages (ALERT, CRITICAL, etc.). Mapping is
        mostly straightforward. """
        assert level >= 0
        if level >= logging.DEBUG:
            # level is already a logging-compatible value
            return level
        if level > LOG_DEBUG:
            return logging.DEBUG
        return [
            logging.CRITICAL,  # syslog.LOG_EMERG
            logging.CRITICAL,  # syslog.LOG_ALERT,
            logging.CRITICAL,  # syslog.LOG_CRIT,
            logging.ERROR,     # syslog.LOG_ERR,
            logging.WARNING,   # syslog.LOG_WARNING,
            _NOTICE,           # syslog.LOG_NOTICE,
            logging.INFO,      # syslog.LOG_INFO,
            logging.DEBUG,     # syslog.LOG_DEBUG
        ][level]

    @classmethod
    def update_handler(cls, handler=None, level=None, verbose=False):
        root = logging.getLogger()
        if level is not None:
            if not isinstance(level, int):
                try:
                    level = LOG_LEVELS.index(level)
                except ValueError:
                    # log level name not found
                    cls.log(logging.WARNING,
                            "invalid log level: '%s'" % (level, ))
                    level = None
            if level is not None:
                cls._log.setLevel(cls._get_logging_level(level))
        if handler or verbose:
            if handler:
                if cls._log_handler:
                    root.removeHandler(cls._log_handler)
                cls._log_handler = handler
                root.addHandler(handler)
            cls._log_handler.setFormatter(
                cls._log_verbose if verbose else cls._log_formatter)
            cls.log(logging.DEBUG,
                    "set default log handler to %s" % (handler, ))
        # Don't emit a 'log level changed' message if we haven't installed
        # a handler, to avoid annoying 'no handler available' messages.
        if level is not None and cls._log_handler:
            cls.log(_NOTICE,
                    "set log level to %d" % (cls._log.getEffectiveLevel(), ),
                    # use tb_offset=3 to omit this stack frame in output
                    tb_offset=3, tb_limit=2)


# set the default logger (can be overridden for testing)
try:
    # in some environments /dev/log is not the syslog socket
    sock = environ.get('CCM_SYSLOG_SOCKET', '/dev/log')
    # and in some cases, e.g., running under Django, we use a handler from,
    # that env, so the empty socket name prevents adding our root handler.
    if sock:
        handler = SysLogHandler(address=sock, facility=LOG_LOCAL0)
    else:
        handler = None
    DefaultLogger.update_handler(
        handler,
        # note that we're setting the level of the logger, not handler, here
        logging.WARNING)
except IOError as ex:
    if ex.errno == errno.ENOENT:
        # ignoring this error is good for testing, but...
        print("unable to connect to syslog at %s: %s" % (sock, ex),
              file=stderr)
    else:
        raise


# these are syslog log levels
LOG_LEVELS = ['EMERGENCY', 'ALERT', 'CRITICAL', 'ERROR', 'WARNING', 'NOTICE',
              'INFO', 'DEBUG']


def emergency(message, **kwargs):
    """Level 0"""
    _handle_log_event(logging.CRITICAL, message, **kwargs)

def alert(message, **kwargs):
    """Level 1"""
    _handle_log_event(logging.CRITICAL, message, **kwargs)

def critical(message, **kwargs):
    """Level 2"""
    _handle_log_event(logging.CRITICAL, message, **kwargs)

def error(message, **kwargs):
    """Level 3"""
    _handle_log_event(logging.ERROR, message, **kwargs)

def warning(message, **kwargs):
    """Level 4"""
    _handle_log_event(logging.WARNING, message, **kwargs)

def notice(message, **kwargs):
    """Level 5"""
    _handle_log_event(_NOTICE, message, **kwargs)

def info(message, **kwargs):
    """Level 6"""
    _handle_log_event(logging.INFO, message, **kwargs)

def debug(message, **kwargs):
    """Level 7"""
    _handle_log_event(logging.DEBUG, message, **kwargs)

def _handle_log_event(priority, message, **kwargs):
    tb_limit = kwargs.pop('tb_limit', 0)
    # from log() the original caller will be the 4th stack frame back, but
    # we also allow the caller to add an extra offset, e.g., in case of
    # wrapper functions.
    tb_offset = kwargs.pop('tb_offset', 0) + 4
    if len(kwargs):
        message = " ".join([message] +
                           [('%s=%s' % (k, v)) for (k, v) in
                            sorted(kwargs.items(), key=lambda i: i[0])])
    DefaultLogger.log(priority, message, tb_offset, tb_limit)


def with_trace(log_fn, message, **kwargs):
    """ Add a traceback to a logger message. """
    kwargs.setdefault('tb_limit', 3)  # 3 additional stack frames by default
    log_fn(message, **kwargs)
