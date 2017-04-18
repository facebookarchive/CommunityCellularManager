"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from sys import exc_info

class VTYException(Exception):
    pass

class VTYChainedException(VTYException):
    """
    Wrap errors raised by the VTY socket connection so they can be caught
    without needing to know all the types of exceptions that it can raise
    """
    def __init__(self, inner):

        super(VTYException, self).__init__(
            "chained exception - %s(%s): %s" %
            (inner.__class__.__name__, inner, exc_info()[2]))
