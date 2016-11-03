""" Direct logging output to stdout during testing.

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

from logging import StreamHandler, DEBUG
# use stdout for output since nosetests will swallow it
from sys import stdout

from ccm.common.logger import DefaultLogger, notice

DefaultLogger.update_handler(StreamHandler(stdout), DEBUG)
notice("directing logger output to stdout during testing")
