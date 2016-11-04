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

import envoy
import requests
import requests.exceptions
import snowflake

from ccm.common import logger
from core import system_utilities
from core.bts import bts
from core.exceptions import BSSError
from core.config_database import ConfigDB
from core.servicecontrol import ServiceState
from core.service import Service

conf = ConfigDB()
# Dependent supervisor service names for start/stop.
SERVICES = bts.SERVICES + [Service.SupervisorService('openvpn'),
                           Service.SystemService('freeswitch'),
                           Service.SupervisorService('endagad')]


def get_registration_conf():
    """Attempts to get registration config information from the cloud.

    Returns:
      the config data

    Raises:
      ValueError if the request does not return 200
    """
    params = {
        'bts_uuid': snowflake.snowflake()
    }
    r = requests.get(conf['registry'] + "/bts/sslconf", params=params)
    if r.status_code == 200:
        return json.loads(r.text)
    else:
        raise ValueError("Getting reg conf failed with status %d" %
                         r.status_code)


def get_vpn_conf(eapi, csr):
    data = {
        'bts_uuid': snowflake.snowflake(),
        'csr': csr
    }
    registration = conf['registry'] + '/bts/register'
    try:
        r = requests.post(registration, data=data, headers=eapi.auth_header)
        if r.status_code == 200:
            return json.loads(r.text)
        else:
            err = ("VPN conf/cert signing failed with status %d (%s)" %
                   (r.status_code, r.text))
    except socket.error as ex:
        err = ("socket error connecting to %s: %s" % (registration, ex))
    except requests.exceptions.RequestException as ex:
        err = ("request to %s failed: %s" % (registration, ex))
    logger.error(err)
    raise ValueError(err)


def register_update(eapi):
    """Ensures the inbound URL for the BTS is up to date."""
    vpn_ip = system_utilities.get_vpn_ip()
    vpn_status = "up" if vpn_ip else "down"

    # This could fail when offline! Must handle connection exceptions.
    try:
        params = {
            'bts_uuid': snowflake.snowflake(),
            'vpn_status': vpn_status,
            'vpn_ip': vpn_ip,
            # federer always runs on port 80, but didn't in old versions
            'federer_port': "80",
        }
        r = requests.get(conf['registry'] + "/bts/register", params=params,
                         headers=eapi.auth_header, timeout=11)
        if r.status_code == 200:
            try:
                d = json.loads(r.text)
                if 'bts_secret' in d:
                    conf['bts_secret'] = d['bts_secret']
            except ValueError:
                pass
            return r.text
        else:
            raise ValueError("BTS registration update failed with status"
                             " %d (%s)" % (r.status_code, r.text))
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        logger.error("register_update failed due to connection error or"
                      " timeout.")


def generate_keys():
    """Attempt to get keys with a backoff period."""
    # Exit if we're already registered.
    if 'bts_registered' in conf and conf['bts_registered']:
        return
    backoff_count = 0
    while not ('endaga_token' in conf and conf['endaga_token']):
        try:
            reg = get_registration_conf()
            conf['endaga_token'] = reg['token']
            conf['sslconf'] = reg['sslconf']
        except ValueError:
            time.sleep(min(2**backoff_count, 300))
            backoff_count += 1
            continue
        # generate keys and csr
        with open("/etc/openvpn/endaga-sslconf.conf.noauto", "w") as f:
            f.write(conf['sslconf'])
        envoy.run("openssl req -new -newkey rsa:2048"
                  " -config /etc/openvpn/endaga-sslconf.conf.noauto"
                  " -keyout /etc/openvpn/endaga-client.key"
                  " -out /etc/openvpn/endaga-client.req -nodes")


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
        # Send on the CSR and keep trying to register.
        backoff_count = 0
        with open("/etc/openvpn/endaga-client.req") as f:
            csr = f.read()
        while not ('bts_registered' in conf and conf['bts_registered']):
            try:
                vpn = get_vpn_conf(eapi, csr)
                cert = vpn['certificate']
                vpnconf = vpn['vpnconf']
                assert len(vpnconf) > 0 and len(cert) > 0,'Empty VPN Response'
                with open('/etc/openvpn/endaga-client.crt', 'w') as f:
                    f.write(cert)
                with open('/etc/openvpn/endaga-vpn-client.conf.noauto', 'w') as f:
                    f.write(vpnconf)
                conf['bts_registered'] = True
            except ValueError:
                delay = min(2**backoff_count, 300)
                logger.info("registration failed, sleeping %d seconds" %
                            (delay, ))
                time.sleep(delay)
                backoff_count += 1


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
        logger.error("BTS is not yet registered, skipping VPN setup, killing"
                      " all services.")
        for s in SERVICES:
            if s.name == "endagad":
                continue
            s.stop()
        return

    # If the VPN is down, try to start it, then restart FS if we succeed.
    if not system_utilities.get_vpn_ip():
        max_attempts = 10
        for _ in range(0, max_attempts):
            # Sometimes the vpn service is started, but the VPN is still down.
            # If this is the case, stop the vpn service first.
            openvpn_service = Service.SupervisorService("openvpn")
            if openvpn_service.status() == ServiceState.Running:
                openvpn_service.stop()
            if (openvpn_service.start()
                and system_utilities.get_vpn_ip()):
                logger.notice("VPN up restarting services")
                Service.SystemService("freeswitch").restart()
            else:
                logger.error("VPN didn't come up after registration,"
                              " retrying.")
                time.sleep(3)
        if not system_utilities.get_vpn_ip():
            logger.error("Failed to set up VPN after %d attempts!" %
                          max_attempts)
    # Start all the other services.  This is safe to run if services are
    # already started.
    for s in SERVICES:
        s.start()

def ensure_fs_external_bound_to_vpn():
    # Make sure that we're bound to the VPN IP on the external sofia profile,
    # assuming the VPN is up.
    vpn_ip = system_utilities.get_vpn_ip()
    if not vpn_ip:
        return
    external_profile_ip = system_utilities.get_fs_profile_ip('external')
    if external_profile_ip != vpn_ip: # TODO: treat these as netaddr, not string
        logger.warning("external profile should be bound to VPN IP and isn't, "
                       "restarting FS.")
        Service.SystemService("freeswitch").restart()

def clear_old_pid(pname="OpenBTS", path="/var/run/OpenBTS.pid"):
    # If the pid file specified doesn't match a running instance of the
    # process, remove the PID file. This is a workaround for a recurring
    # OpenBTS issue we see. Note, caller must have permissions to remove file.

    # Determine PIDs associated with pname
    output = envoy.run("ps -A | grep OpenBTS")
    pids = []
    for line in output.std_out.split('\n'):
        try:
            pids.append(int(line.strip().split()[0]))
        except ValueError:
            continue # not a pid, so ignore it
        except IndexError:
            continue # malformed, ignore

    try:
        with open(path, "r") as f:
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
            raise ValueError("invalid registry URL: %s" % (registry, ))
        conf['registry'] = registry
    # Remove the relevant endaga config keys.
    del conf['bts_registered']  # registration status
    del conf['bts_secret']  # the temporary key for authing requests
    del conf['sslconf']  # ssl configuration
    conf['endaga_token'] = None  # the account owner's API token
    # Remove the vpn configuration and keys.
    for f in ["endaga-client.key", "endaga-client.crt", "endaga-client.req",
              "endaga-sslconf.conf.noauto", "endaga-vpn-client.conf.noauto"]:
        fpath = "/etc/openvpn/%s" % f
        if os.path.exists(fpath):
            os.remove(fpath)
    # Stop all other services and restart endagad.
    for s in SERVICES:
        if s.name == "endagad":
            continue
        s.stop()
    Service.SupervisorService("endagad").restart()

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
