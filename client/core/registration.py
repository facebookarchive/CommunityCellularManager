"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.

BTS registration and checkin control.

Make sure we're connected to the VPN and can reach internal API server. If so,
continue launching everything else.

1) Send UUID, see if registration is needed.
    - Response:
        - need_to_register: True/False. If false, no further
"""

import json
import os
import socket
import time

import delegator
import requests
from requests.exceptions import RequestException
from snowflake import snowflake

from ccm.common import logger
from core import system_utilities
from core.bts import bts
from core.config_database import ConfigDB
from core.servicecontrol import ServiceState
from core.service import Service


conf = ConfigDB()
# Dependent supervisor service names for start/stop.
SERVICES = bts.SERVICES + [Service.SupervisorService('openvpn'),
                           Service.SystemService('freeswitch'),
                           Service.SupervisorService('endagad')]


class RegistrationError(Exception):
    def __init__(self, prefix, msg):
        super(RegistrationError, self).__init__(
            '%s: %s' % (prefix, msg) if prefix else msg)


class RegistrationClientError(RegistrationError):
    """ Exception was raised by client (could be socket, requests, etc.) """
    def __init__(self, msg, ex, prefix=None):
        super(RegistrationClientError, self).__init__(
            prefix, msg + (': %s' % (ex, )))
        self.exception = ex


class RegistrationServerError(RegistrationError):
    """ Error was returned by server """
    def __init__(self, resp, prefix=None):
        msg = ('server returned status %d (%s)' %
               (resp.status_code,
                (resp.text if len(resp.text) < 100 else
                 '%s <%d bytes truncated>' %
                 (resp.text[:100], len(resp.text))
                )
               )
              )
        super(RegistrationServerError, self).__init__(prefix, msg)
        self.status_code = resp.status_code
        self.text = resp.text


def _send_cloud_req(req_method, req_path, err_prefix, **kwargs):
    url = conf['registry'] + req_path
    err = None
    try:
        r = req_method(url, **kwargs)
        if r.status_code == 200:
            return json.loads(r.text)
        else:
            err = RegistrationServerError(r, err_prefix)
    except socket.error as ex:
        err = RegistrationClientError(('socket error connecting to %s' %
                                       (url, )),
                                      ex, err_prefix)
    except RequestException as ex:
        err = RegistrationClientError('request to %s failed' % (url, ),
                                      ex, err_prefix)
    raise err


def _get_snowflake():
    """ Read UUID from /etc/snowflake. If it doesn't exist, die. """
    bts_uuid = snowflake()
    if bts_uuid:
        return bts_uuid

    SNOWFLAKE_MISSING = '/etc/snowflake missing'
    logger.critical(SNOWFLAKE_MISSING)
    raise SystemExit(SNOWFLAKE_MISSING)


def get_registration_conf():
    """Attempts to get registration config information from the cloud.

    Returns:
      the config data

    Raises:
      RegistrationError if the request does not return 200
    """
    bts_uuid = _get_snowflake()
    params = {
        'bts_uuid': bts_uuid
    }
    try:
        return _send_cloud_req(
            requests.get,
            '/bts/sslconf',
            'get cert config',
            params=params)
    except RegistrationServerError as ex:
        if ex.status_code == 403:
            msg = 'BTS already registered - manually generate new snowflake'
            # unrecoverable error - exit
            logger.critical(msg)
            raise SystemExit(msg)
        if ex.status_code == 404:
            logger.warning('*** ensure BTS UUID (%s) is registered' %
                           (bts_uuid, ))
        raise


def get_vpn_conf(eapi, csr):
    data = {
        'bts_uuid': _get_snowflake(),
        'csr': csr
    }
    try:
        return _send_cloud_req(
            requests.post,
            '/bts/register',
            'get VPN config',
            data=data, headers=eapi.auth_header)
    except RegistrationServerError as ex:
        if ex.status_code == 400 and ex.text == '"status: 500"':
            logger.warning('*** internal certifier error, reset snowflake?')
        raise


def register_update(eapi):
    """Ensures the inbound URL for the BTS is up to date."""
    vpn_ip = system_utilities.get_vpn_ip()
    vpn_status = 'up' if vpn_ip else 'down'

    # This could fail when offline! Must handle connection exceptions.
    params = {
        'bts_uuid': _get_snowflake(),
        'vpn_status': vpn_status,
        'vpn_ip': vpn_ip,
        'federer_port': '80',
    }
    try:
        d = _send_cloud_req(
            requests.get,
            '/bts/register',
            'BTS registration',
            params=params,
            headers=eapi.auth_header,
            timeout=11)
        if 'bts_secret' in d:
            conf['bts_secret'] = d['bts_secret']
    except RegistrationError as ex:
        logger.error(str(ex))


def _retry_req(req, err_prefix):
    # retry request until request succeeds
    backoff_count = 0
    while True:
        try:
            return req()
        except RegistrationError as ex:
            delay = min(2**backoff_count, 300)
            logger.with_trace(
                logger.error,
                ('%s failed - %s - sleeping %d seconds' %
                 (err_prefix, ex, delay)),
                tb_limit=0,
                tb_offset=2)
            time.sleep(delay)
            backoff_count += 1


def _reset_endaga_token():
    conf['endaga_token'] = None


def generate_keys():
    """Attempt to get keys with a backoff period."""
    # Exit if we're already registered.
    if 'bts_registered' in conf and conf['bts_registered']:
        return

    # not registered - discard old token before getting a new one
    _reset_endaga_token()

    reg = _retry_req(get_registration_conf, 'generate keys')
    conf['endaga_token'] = reg['token']
    sslconf = reg['sslconf']

    # generate keys and csr
    with open('/etc/openvpn/endaga-sslconf.conf.noauto', 'w') as f:
        f.write(sslconf)
    delegator.run('openssl req -new -newkey rsa:2048'
              ' -config /etc/openvpn/endaga-sslconf.conf.noauto'
              ' -keyout /etc/openvpn/endaga-client.key'
              ' -out /etc/openvpn/endaga-client.req -nodes')


def register(eapi):
    """
    After a call to this, BTS should be registered with the server and have all
    credentials to connect to VPN.

    "Registered" here means that we have gotten our CSR (created by
    generate_keys()) signed by the server, and have received a signed
    certificate and client configuration back from the server. We'll stay stuck
    here trying to get our key signed until we succeed.

    A device is associated with an account in get_registration_conf(); if this
    fails, then the device won't have access credentials for our API and none
    of this will succeed. A device that is associated with an account, but for
    some reason can't get VPN credentials, will get stuck here, but local
    services will still work.
    """

    if not ('bts_registered' in conf and conf['bts_registered']):
        # We're not registered yet, so do the initial registration procedure.
        OPENVPN_DIR = '/etc/openvpn/endaga-'
        CLIENT_CERT = OPENVPN_DIR + 'client.crt'
        VPN_CONF = OPENVPN_DIR + 'vpn-client.conf.noauto'

        # If we don't have a client certificate (signed by the certifier)
        # and VPN config file then attempt to get them by registering.
        if not (os.path.exists(CLIENT_CERT) and os.path.exists(VPN_CONF)):
            # Send the CSR and keep trying to register.
            with open(OPENVPN_DIR + 'client.req') as f:
                csr = f.read()

            vpn = _retry_req(lambda: get_vpn_conf(eapi, csr),
                             'BTS registration')
            cert = vpn['certificate']
            vpnconf = vpn['vpnconf']
            assert len(vpnconf) > 0 and len(cert) > 0, 'Invalid VPN parameters'
            logger.info('got VPN configuration')
            # write the client cert (before verification, for troubleshooting)
            with open(CLIENT_CERT, 'w') as f:
                f.write(cert)
            # write the VPN config (don't discard if cert verification fails)
            with open(VPN_CONF, 'w') as f:
                f.write(vpnconf)
        else:
            # We already have a cert and VPN conf from a previous
            # attempt to register, but the cert could not be validated
            # against the CA bundle and that attempt aborted. The
            # user should be able to replace the CA bundle
            # (etage-bundle.crt) with the one that corresponds to the
            # cloud installation, after which registration should
            # succeed.
            with open(CLIENT_CERT, 'r') as f:
                cert = f.read()

        # validate client cert against CA
        cert_verified = False
        cert_dir = os.path.dirname(VPN_CONF)
        cert_path = os.path.join(cert_dir, 'endaga-client.crt')
        for c in ['etage-bundle.local.crt', 'etage-bundle.crt']:
            ca_path = os.path.join(cert_dir, c)
            if system_utilities.verify_cert(cert, cert_path, ca_path):
                logger.info("Verified client cert against CA %s" % (ca_path, ))
                cert_verified = True
                break
        if not cert_verified:
            """
            Any error requires manual intervention, i.e., updating the CA
            cert, and hence cannot be resolved by retrying
            registration. Therefore we just raise an exception that
            terminates the agent.
            """
            raise SystemExit("Unable to verify client cert, terminating")

        conf['bts_registered'] = True


def update_vpn():
    """
    If the BTS is registered, try to start the VPN. If the BTS is not
    registered, skip.

    If the BTS is unregistered (on the dashboard), no services are available.

    Regardless of whether the VPN is up or down, all services should be started
    (this will enable disconnected operation). However, when the VPN comes
    online, we need to restart FS to make sure that we're bound to the VPN IP
    so outgoing calls can work.
    """
    if not ('bts_registered' in conf and conf['bts_registered']):
        logger.error('BTS is not yet registered, skipping VPN setup, killing'
                      ' all services.')
        for s in SERVICES:
            if s.name == 'endagad':
                continue
            s.stop()
        return

    # If the VPN is down, try to start it, then restart FS if we succeed.
    if not system_utilities.get_vpn_ip():
        max_attempts = 10
        for _ in range(0, max_attempts):
            # Sometimes the vpn service is started, but the VPN is still down.
            # If this is the case, stop the vpn service first.
            openvpn_service = Service.SupervisorService('openvpn')
            if openvpn_service.status() == ServiceState.Running:
                openvpn_service.stop()
            if openvpn_service.start():
                logger.notice('VPN service started')
                if system_utilities.get_vpn_ip():
                    logger.notice('VPN up - restarting freeswitch')
                    Service.SystemService('freeswitch').restart()
                else:
                    logger.error('VPN interface (%s) is down' %
                                 conf.get('external_interface'))
            else:
                logger.error(
                    'VPN failed to start after registration, retrying.')
                time.sleep(3)
        if not system_utilities.get_vpn_ip():
            logger.error('Failed to set up VPN after %d attempts!' %
                          max_attempts)
    # Start all the other services.  This is safe to run if services are
    # already started.
    for s in SERVICES:
        try:
            s.start()
        except Exception as e:
            logger.critical("Exception %s while starting %s" % (e, s.name))

def ensure_fs_external_bound_to_vpn():
    # Make sure that we're bound to the VPN IP on the external sofia profile,
    # assuming the VPN is up.
    vpn_ip = system_utilities.get_vpn_ip()
    if not vpn_ip:
        return
    external_profile_ip = system_utilities.get_fs_profile_ip('external')
    if external_profile_ip != vpn_ip: # TODO: treat these as netaddr, not string
        logger.warning('external profile should be bound to VPN IP and isn\'t,'
                       ' restarting FS.')
        Service.SystemService('freeswitch').restart()

def clear_old_pid(pname='OpenBTS', path='/var/run/OpenBTS.pid'):
    # If the pid file specified doesn't match a running instance of the
    # process, remove the PID file. This is a workaround for a recurring
    # OpenBTS issue we see. Note, caller must have permissions to remove file.

    # Determine PIDs associated with pname
    c = delegator.run('ps -A | grep OpenBTS')
    if c.return_code != 0:
        return

    pids = []
    for line in c.out.split('\n'):
        try:
            pids.append(int(line.strip().split()[0]))
        except ValueError:
            continue # not a pid, so ignore it
        except IndexError:
            continue # malformed, ignore

    try:
        with open(path, 'r') as f:
            pid = int(f.read().strip())
    except IOError:
        # File does not exist, probably.
        return

    if pid not in pids:
        os.remove(path)

def reset_registration(registry=None):
    """Removes existing registration but does not erase the snowflake UUID."""
    if registry:
        if not ((registry.startswith('http://') or
                 registry.startswith('https://')) and
                registry.endswith('/api/v1')):
            raise ValueError('invalid registry URL: %s' % (registry, ))
        conf['registry'] = registry
    # Remove the relevant endaga config keys.
    del conf['bts_registered']  # registration status
    del conf['bts_secret']  # the temporary key for authing requests
    _reset_endaga_token()  # the account owner's API token
    # Remove the vpn configuration and keys.
    for f in ['endaga-client.key', 'endaga-client.crt', 'endaga-client.req',
              'endaga-sslconf.conf.noauto', 'endaga-vpn-client.conf.noauto']:
        fpath = '/etc/openvpn/%s' % f
        if os.path.exists(fpath):
            os.remove(fpath)
    # Stop all other services and restart endagad.
    for s in SERVICES:
        if s.name == 'endagad':
            continue
        s.stop()
    Service.SupervisorService('endagad').restart()

def system_healthcheck(checkin_data):
    # A generic "health check" on the system. Currently, we just see if
    # there are zero active users camped to the system.  Returns True if
    # system is fine, False otherwise.
    status = checkin_data['status']
    try:
        if len(status['camped_subscribers']) == 0:
            return False
        if len(status['openbts_load']) == 0:
            return False
    except KeyError:
        return False # missing keys, there's a problem
    return True
