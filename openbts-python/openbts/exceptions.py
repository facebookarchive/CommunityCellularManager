"""openbts.exceptions
core exceptions raised by the client

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

class OpenBTSError(Exception):
  """Generic package error."""
  pass

class InvalidRequestError(OpenBTSError):
  """Raised upon invalid requests to Node Manager."""
  pass

class InvalidResponseError(OpenBTSError):
  """Invalid zmq response."""
  pass

class MalformedResponseError(OpenBTSError):
  """Invalid response body from OpenBTS"""
  pass

class TimeoutError(OpenBTSError):
  """Zmq socket timeout."""
  pass
