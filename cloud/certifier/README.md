
Certifier
=========

This is a simple HTTP API for OpenVPN TLS certificate signing. It should *not*
ever be put on a public machine. Similar in principle to
[cfssl](https://github.com/cloudflare/cfssl), this does no enforcement of
policy, and simply signs any CSR it gets.

Underneath, we shell out to [easyrsa](https://github.com/OpenVPN/easy-rsa) to
handle all the dirty work. While this isn't a great idea, it's probably fine
for now.

The major limitation right now is that we are storing a lot of state as files
on disk. At minimum, we should back key files up somewhere, specifically the
serial number and index of certificates. We should also keep track of the certs
themselves so we can perform certificate revocation.

API
---

**/ping**

- GET: Returns 200 OK if the server is up

**/csr**

- POST
  - Requires:
     - ident: A globally unique identifier for the client (UUID)
     - csr: A string representing a certificate signing request
  - Returns a JSON-encoded response with the following keys:
        - certificate: The string representing the signed certificate.

To generate a CSR run scripts/gen_csr.py from the webserver.
To test the certifier:
   curl --form ident=84bc2563-2da1-4924-91cc-86b4d19ebf55 --form csr=@client.req localhost/csr


Deployment
----------
This is to be deployed on our keymaster, which is only internally accessible.
Run `ansible-playbook -i hosts certifier.yml` to actually deploy it. Note that
you must manually update the VERSION file in this directory to deploy a new
version on the server.

The server side private key is encrypted. It's an intermediate key from the
root CA.
