# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from core.config_database import ConfigDB

#
# Override stubs with system specific implementation
#
conf = ConfigDB()

if conf['bts.type'] == 'fake':
    from . import _fakehlr
    subscriber = _fakehlr.FakeSubscriberDB()
elif conf['bts.type'] == 'osmocom':
    from . import _osmocom
    subscriber = _osmocom.OsmocomSubscriber()
else:
    from . import _openbts
    subscriber = _openbts.OpenBTSSubscriber()
