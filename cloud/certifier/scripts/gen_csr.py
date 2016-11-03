"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

#!/usr/bin/python

import json
import uuid
import requests
import envoy
import argparse

p = argparse.ArgumentParser(description='Generate a Certificate Signing Request')
p.add_argument('--new', dest='new', action="store_const", 
               const=True, default=False, help='Generate new UUID')

args = p.parse_args()

iden = None
if (args.new):
    iden = uuid.uuid4()
else:
    iden = "84bc2563-2da1-4924-91cc-86b4d19ebf55"

raw_input("Register BTS %s into the web interface. Press enter when done." % iden)

params = {
    'bts_uuid': iden
}
r = requests.get("http://127.0.0.1:8080/api/v1/bts/sslconf", params=params)
if (r.status_code != 200):
    raise Exception("Unable to generate ssl conf")

sslconf = json.loads(r.text)['sslconf']
with open("sslconf.conf", "w") as f:
    f.write(sslconf)

envoy.run("openssl req -new -newkey rsa:2048"
          " -config sslconf.conf"
          " -keyout client.key"
          " -out client.req -nodes")
