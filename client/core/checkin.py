"""
Handle checkin responses.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






import json

from ccm.common import delta, logger
from core.billing import process_prices
from core.bts import bts
from core.config_database import ConfigDB
from core.event_store import EventStore
from core.registration import reset_registration
from core.subscriber import subscriber


class CheckinHandler(object):

    CONFIG_SECTION = "config"
    EVENTS_SECTION = "events"
    SUBSCRIBERS_SECTION = "subscribers"

    # NOTE: Keys in section_ctx dictionary below must match the keys of
    # optimized checkin sections: "config", "events", "subscribers", etc.
    section_ctx = {
        CONFIG_SECTION: delta.DeltaProtocolCtx(),
        # Note: EVENTS_SECTION is not optimized
        SUBSCRIBERS_SECTION: delta.DeltaProtocolCtx(),
    }

    def __init__(self, response):
        self.conf = ConfigDB()
        self.eventstore = EventStore()
        r = self.validate(response)
        self.process(r)

    def process(self, resp_dict):
        """Process sections of a checkin response.

        Right now we have three sections: config, events, and subscribers.
        """
        if 'status' in resp_dict and resp_dict['status'] == 'deregistered':
            reset_registration()
        for section in resp_dict:
            if section == CheckinHandler.CONFIG_SECTION:
                self.process_config(resp_dict[section])
            elif section == CheckinHandler.EVENTS_SECTION:
                self.process_events(resp_dict[section])
            elif section == CheckinHandler.SUBSCRIBERS_SECTION:
                self.process_subscribers(resp_dict[section])
            elif section != 'status':
                logger.error("Unexpected checkin section: %s" % section)

    def validate(self, response):
        """Validates a response.

        Args:
          response: decoded json response from the server as a python
                    dictionary.

        Returns: a python dictionary containing the checkin response, otherwise
                 throws errors.
        """
        r = json.loads(response)
        return r['response']

    @delta.DeltaCapable(section_ctx['config'], True)
    def process_config(self, config_dict):
        for section in config_dict:
            if section == "endaga":
                self.conf.process_config_update(config_dict[section])
            # TODO cloud should use generic key names not openbts specific
            elif section == "openbts":
                bts.process_bts_settings(config_dict[section])
            elif section == "prices":
                process_prices(config_dict['prices'], self.conf)
            elif section == "autoupgrade":
                self.process_autoupgrade(config_dict['autoupgrade'])

    # wrap the subscriber method in order to keep delta context encapsulated
    @delta.DeltaCapable(section_ctx['subscribers'], True)
    def process_subscribers(self, data_dict):
        subscriber.process_update(data_dict)

    def process_events(self, data_dict):
        """Process information about events.

        Right now, there should only be one value here: seqno, which denotes
        the highest seqno for this BTS for which the server has ack'd.
        """
        if "seqno" in data_dict:
            seqno = int(data_dict['seqno'])
            self.eventstore.ack(seqno)

    def process_autoupgrade(self, data):
        """Process information about autoupgrade preferences.

        Args:
          data: a dict of the form {
            'enabled': True,
            'channel': 'dev',
            'in_window': True,  # whether to upgrade in a window or not.  If
                                # not, this means we should upgrade as soon as
                                # new packages are available.
            'window_start': '02:45:00'
            'latest_stable_version': '1.2.3',
            'latest_beta_version': '5.6.7',
          }

        The configdb keys are prefixed with "autoupgrade." (e.g.
        autoupgrade.enabled).
        """
        for key in ('enabled', 'channel', 'in_window', 'window_start',
                    'latest_stable_version', 'latest_beta_version'):
            configdb_key = 'autoupgrade.%s' % key
            # Set the value if it's not already in the config db or if it's
            # changed.
            existing_value = self.conf.get(configdb_key, None)
            if existing_value != data[key]:
                self.conf[configdb_key] = data[key]
