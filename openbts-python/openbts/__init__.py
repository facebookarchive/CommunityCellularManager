"""openbts
python client to the OpenBTS NodeManager

NodeManager provides an API to other components in the OpenBTS application
suite, such as the SMQueue service, SIPAuthServe, OpenBTS and NodeManager
itself.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from .components import OpenBTS, SIPAuthServe, SMQueue
