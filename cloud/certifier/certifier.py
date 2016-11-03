"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import time
import uuid

import envoy
import web

"""
This is a simple service to automate signing of OpenVPN credentials. It does no
enforcement of any policy, and *MUST* be deployed to be inaccessible from
untrusted machines.

"""

def sign_csr(client_csr_data, ident):
    """
    Given a CSR, sign the certificate with our private key and return a json response.
    """
    ident = "%s-%s" % (ident, int(time.time()))
    # first, create a tmp copy of the csr
    client_csr = "/tmp/client-%s.req" % ident
    with open(client_csr, "w") as f:
        f.write(client_csr_data)

    easyrsa_import_cmd = "./easyrsa import-req /tmp/client-%s.req client-%s" % (ident, ident)
    #envoy is interpreting this as a list for some reason -kurtis
    r = envoy.run(str(easyrsa_import_cmd))
    if (r.status_code != 0):
        raise Exception("Import-req failed: %s" % r.std_err)

    #csr_sign_cmd_str = "openssl x509 -req -days 3650 -in %s -CA %s -CAkey %s -set_serial %d -out %s" % (client_csr, config.ca_crt, config.ca_key, serial, client_crt)

    # write a new serial file
    with open('pki/serial', 'w') as f:
        f.write(uuid.uuid4().hex)

    easyrsa_sign_cmd = "./easyrsa --batch sign-req client client-%s" % ident
    r = envoy.run(str(easyrsa_sign_cmd))
    if (r.status_code != 0):
        raise Exception("sign-req failed")

    client_crt = "pki/issued/client-%s.crt" % ident
    with open(str(client_crt), "r") as crt:
        resp = ""
        for line in crt:
            resp += line
        return resp

urls = ("/csr", "csr",
        "/ping", "ping")

class ping(object):
    def GET(self):
        web.header('Content-Type', "application/json")
        return json.dumps({'status': 'ok'})

class csr(object):
    def GET(self):
        raise web.Forbidden()

    def POST(self):
        data = web.input()
        if not ("ident" in data and "csr" in data):
            raise web.BadRequest()

        crt = sign_csr(data.csr, data.ident)
        web.header('Content-Type', "application/json")
        return json.dumps({'certificate': crt})

app = web.application(urls, locals())

if __name__ == "__main__":
    app.run()
