"""Main loop for endagad.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import time

from requests.exceptions import ConnectionError, Timeout

from ccm.common import logger
from core import interconnect, system_utilities
from core.bts import bts
from core.config_database import ConfigDB
from core.exceptions import BSSError
from core import registration
from core.service import Service


class EndagaD(object):
    """
    Thin wrapper around the main loop that communicates with the cloud
    service. Manages registration, checkin and associated responses.
    """
    def __init__(self):
        self._conf = ConfigDB()
        # initialise logging level from DB (if set - otherwise 'warning')
        # NB - this is the ONLY time changes to the log level are actually
        # passed to the logging framework
        log_level = self._conf.get("logger.global.log_level", "warning")
        logger.DefaultLogger.update_handler(level=log_level)
        logger.notice("EndagaD started")

    def _reset_bts_config(self):
        logger.notice("Performing set_factory")
        try:
            if bts.set_factory_config():
                logger.notice("Restarting BTS")
                bts.restart()
                Service.SystemService("freeswitch").restart()
        except BSSError as e:
            logger.error("bts is probably down: %s" % e)
        except Exception as e:
            # OSError, IOError or whatever envoy will raise
            logger.critical("something unexpected happened: %s" % e)

    def run(self):
        """
        Main loop for endagad. This moves the system through the various
        states of operation -- it should be a state machine really!

        General flow is:
        1) Tries to get configuration from server to produce VPN keys
        2) Generates keys locally.
        3) Sends CSR for signing, returns that.
        4) Starts system services (FS, BTS, etc) and configures them
        appropriately. Note configuration can change depending on registration
        and VPN state of the system.
        5) Runs checkin periodically.
        """
        eapi = interconnect.endaga_ic(self._conf)
        if 'registration_interval' not in self._conf:
            self._conf['registration_interval'] = 60

        UNHEALTHY_THRESH = self._conf.get('bts.unhealthy_threshold', 3)
        unhealthy_count = UNHEALTHY_THRESH  # fail quickly on first pass
        while True:
            # Retrieve keys/tokens, or do nothing if we have them.
            logger.notice("Performing gen_keys")
            registration.generate_keys()

            # generate_keys() loads auth token on success. Need to update the
            # interconnect client's token if so.
            if eapi.token is None:
                eapi.token = self._conf['endaga_token']

            # Try to register/get VPN credentials.  Tries forever if fails.
            logger.notice("Performing register")
            registration.register(eapi)

            # Registered, start services and tries to start VPN.  Stop
            # everything otherwise.
            logger.notice("Performing clear_pid")
            registration.clear_old_pid()
            logger.notice("Performing update_vpn")
            registration.update_vpn()

            # At this point, all services should be up, so we can perform
            # additional configuration.
            self._reset_bts_config()

            # Update the inbound_url if the VPN is up.
            if system_utilities.get_vpn_ip() is not None:
                logger.notice("Performing register_update")
                registration.register_update(eapi)
                logger.notice("Performing ensure_fs_external_bound")
                registration.ensure_fs_external_bound_to_vpn()

            # Send checkin to cloud
            try:
                # Sends events, tries to get config info. Can proceed w/o VPN.
                logger.notice("Performing checkin.")
                checkin_data = eapi.checkin(timeout=30)
                logger.notice("Performing system health check.")
                if not registration.system_healthcheck(checkin_data):
                    unhealthy_count += 1
                    logger.notice("System unhealthy: %d" % unhealthy_count)
                else:
                    unhealthy_count = 0
            except (ConnectionError, Timeout):
                logger.error(
                    "checkin failed due to connection error or timeout.")
            except BSSError as e:
                logger.error("bts exception: %s" % e)

            if unhealthy_count > UNHEALTHY_THRESH:
                logger.notice("BTS seems unhealthy, restarting BTS services.")
                bts.restart()
                Service.SystemService("freeswitch").restart()

            # Upgrade the endaga metapackage, when appropriate and only if that
            # feature is enabled.
            logger.notice("Performing autoupgrade")
            system_utilities.try_to_autoupgrade()

            # Sleep for some amount of time before retrying
            logger.notice("Performing sleep")
            time.sleep(self._conf['registration_interval'])


if __name__ == "__main__":
    EndagaD().run()
