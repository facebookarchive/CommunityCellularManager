"""A configuration storage system.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






from ccm.common import logger
from .db.kvstore import KVStore


class ConfigDB(KVStore):
    """A simple database-backed configuration dictionary.

    Stores strings, ints, floats and bools, and strings.
    """
    def __init__(self, connector=None):
        super(ConfigDB, self).__init__('endaga_config', connector)

    @staticmethod
    def _ducktype(value):
        """Very simple typing.

        We try to cast to an integer. If it works, return as an int. If it
        fails, we assume string. If it *exactly* matches "True" or "False" or
        "None", we return as that.
        """
        # Check this first to avoid none-type errors.
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        if value == "True" or value == "true":
            return True
        elif value == "False" or value == "false":
            return False
        else:
            return value

    def __getitem__(self, key):
        return self._ducktype(super(ConfigDB, self).__getitem__(key))

    # pass in something other than None as default, since None is a legit value
    def get(self, key, default=[]):
        ret = super(ConfigDB, self).get(key, default)
        return self._ducktype(ret) if ret != [] else default

    def process_config_update(self, data_dict):
        """Process an endaga settings section in a checkin response.

        This should be a dictionary of key-value pairs. For each pair, we add
        it to the ConfigDB.
        """
        for (key, v) in list(data_dict.items()):
            if key not in self:
                logger.notice("Adding endaga setting: %s -> %s" % (key, v))
            else:
                old_v = self[key]
                if self._ducktype(v) != old_v:
                    logger.notice("Changing endaga setting:"
                                  "%s -> %s (was %s)" % (key, v, old_v))
                else:
                    continue
            self[key] = v


def set_defaults(force_replace=False):
    """Set default keys and values for the ConfigDB.

    Args:
      force_replace: boolean, if True, set the key to the new value even if
                     it's already set in the db.
    """
    defaults = {
        'fs_esl_ip': '127.0.0.1',
        'fs_esl_port': '8021',
        'fs_esl_pass': 'ClueCon',
        'endaga_token': None,
        'registry': 'http://192.168.40.10:8000/api/v1',
        'billing_url': 'http://127.0.0.1/smscdr',
        'free_seconds': 5,
        # General configuration options
        'subscriber_registry': "/var/lib/asterisk/sqlite3dir/sqlite3.db",
        'db_location': "/var/lib/asterisk/sqlite3dir/eventbuf.db",
        # Credit transfer options
        'pending_transfer_db_path': "/tmp/vbts_pending_transfer.sqlite",
        'app_number': 102,
        'credit_check_number': 103,
        'number_check_number': 104,
        'code_length': 4,
        # Localization settings
        'localedir': "/usr/share/locale",
        'locale': "en",
        'currency_code': "USD",
        'number_country': "US",
        # Some subscriber price defaults (overridden in the checkin response).
        'prices.off_network_receive.cost_to_subscriber_per_sms': 0,
        'prices.off_network_receive.cost_to_subscriber_per_min': 0,
        'prices.on_network_receive.cost_to_subscriber_per_sms': 0,
        'prices.on_network_receive.cost_to_subscriber_per_min': 0,
        'prices.off_network_send.1.cost_to_subscriber_per_sms': 0,
        'prices.off_network_send.1.cost_to_subscriber_per_min': 0,
        'prices.on_network_send.cost_to_subscriber_per_sms': 0,
        'prices.on_network_send.cost_to_subscriber_per_min': 0,
        # GPRS event logging settings (all values in seconds).  Records how
        # much time passes before we get data from OpenBTS, how frequently we
        # generate a GPRS usage event, how often we expunge old data from the
        # gprs_records table and the amount of time that must pass before a
        # record is considered 'old.'
        'gprsd_cli_scrape_period': 5,
        'gprsd_event_generation_period': 60,
        'gprsd_cleanup_period': 60 * 60,
        'gprsd_max_data_age': 7 * 24 * 60 * 60,
        # Checkin registration interval
        'registration_interval': 60,
        # Autoupgrade preferences (TZs assumed to be UTC)
        'autoupgrade.enabled': False,
        'autoupgrade.channel': 'stable',
        'autoupgrade.in_window': False,
        'autoupgrade.window_start': '03:30:00',
        'autoupgrade.latest_stable_version': '0.3.25',
        'autoupgrade.latest_beta_version': '0.3.25',
        'autoupgrade.last_upgrade': '2015-07-15 02:30:15',
        # The default logging level.
        'logger.global.log_level': 'WARNING',

        # BTS stack type
        'bts.type': 'openbts',

        # Osmo specific settings
        'bts.osmocom.ip': '127.0.0.1',
        'bts.osmocom.bsc_vty_port': '4242',
        'bts.osmocom.sip_port': '5062',
        'bts.osmocom.hlr_loc': '/var/lib/osmocom/hlr.sqlite3',

        # timeout for all bss sockets and spawned subprocesses
        'bss_timeout': 3,

        # The external interface is the VPN interface we route SIP traffic over
        'external_interface': 'tun0',
        # The internal interface is the NIC used by the BSC/BTS to address this
        # system
        'internal_interface': 'lo'


    }
    config = ConfigDB()
    for key in defaults:
        if (key not in config) or force_replace:
            config[key] = defaults[key]
