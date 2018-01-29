"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

#!/usr/bin/python

import subprocess
import requests
import re
import os
import json

APP_ID = os.environ['FACEBOOK_APP_ID']
APP_SECRET = os.environ['FACEBOOK_APP_SECRET']
ODS_URL = 'https://graph.facebook.com/ods_metrics?access_token=%s|%s' % \
          (APP_ID, APP_SECRET)

SOFIA_STATUS_RE = re.compile("^\s+(\w+)\s(gateway|profile)"
                             "\s+sip:mod_sofia@(\d+\.\d+\.\d+\.\d+:\d+)\s"
                             "(\w+)")
SOFIA_PROFILE_STATUS_RE = re.compile("^([\w|/-]+)\s+(\d+)")

def check_sofia_status(dp):
    res = subprocess.check_output('/usr/bin/fs_cli -x "sofia status"',
                                  shell=True).split("\n")
    for r in res:
        m = SOFIA_STATUS_RE.match(r)
        if (m):
            name = m.group(1)
            typee = m.group(2)
            addr = m.group(3)  # noqa: F841 T25377293 Grandfathered in
            status = m.group(4)
            dp.append({'entity': 'etagecom.cloud.freeswitch.%s.%s' %
                       (name, typee),
                       'key': 'is_active',
                       'value': int(status == "RUNNING")})
            subres = subprocess.check_output('/usr/bin/fs_cli -x '
                                             '"sofia status profile %s"' % (name,),
                                             shell=True).split("\n")
            for t in ["CALLS-IN", "CALLS-OUT"]:
                for subr in subres:
                    if (t in subr):
                        m = SOFIA_PROFILE_STATUS_RE.match(subr)
                        if (m):
                            dp.append({'entity': 'etagecom.cloud.freeswitch.%s.%s' %
                                       (name, typee),
                                       'key': m.group(1),
                                       'value': int(m.group(2))})

NUM_ACTIVE_CALLS_RE = re.compile("^(\d+) total.")
def count_active_calls(dp):
    res = subprocess.check_output('/usr/bin/fs_cli -x "show calls"',
                                  shell=True).split("\n")
    for r in res:
        m = NUM_ACTIVE_CALLS_RE.match(r)
        if (m):
            count = m.group(1)
            dp.append({'entity': 'etagecom.cloud.freeswitch.stats',
                       'key': 'active_calls',
                       'value': int(count)})
            break

datapoints = []
check_sofia_status(datapoints)
count_active_calls(datapoints)
requests.post(ODS_URL, data={'datapoints': json.dumps(datapoints)})
