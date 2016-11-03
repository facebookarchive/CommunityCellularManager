"""openbts.codes
response codes returned by NodeManager

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""
from enum import IntEnum

class OpenBTSCode(IntEnum):
    """Generic OpenBTS response code"""
    pass

class SuccessCode(OpenBTSCode):
    """Codes that are associated with a successful Nodemanager request.
    """
    OK = 200
    NoContent = 204
    NotModified = 304

class ErrorCode(OpenBTSCode):
    """Codes that are associated with a failed Nodemanager request.
    """
    NotFound = 404
    InvalidRequest = 406
    ConflictingValue = 409
    StoreFailed = 500
    UnknownAction = 501
    ServiceUnavailable = 503

