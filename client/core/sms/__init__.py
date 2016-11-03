# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
# 
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant 
# of patent rights can be found in the PATENTS file in the same directory.

from core.config_database import ConfigDB
from . import base

#
# Override stubs with system specific implementation
#
conf = ConfigDB()

if conf['bts.type'] == 'osmocom':
    from .freeswitch import _osmocom
    sms = _osmocom.OsmocomSMS()
else:
    from .freeswitch import _openbts
    sms = _openbts.OpenBTSSMS()
