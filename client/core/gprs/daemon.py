"""Scraping and storing GPRS data.

This main routine is meant to be run as a daemon.  It will do three things
primarily:
 1) gather GPRS usage data via the openbts-python API and drop it into a
    postgres table, 'gprs_records'
 2) generate GPRS usage events for the EventStore
 3) periodically remove old data from 'gprs_records'

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import syslog
import time

from core.config_database import ConfigDB
from core.gprs import utilities


# Set the amount of time to pause between loops.
SLEEP_TIME = 2


def main():
    """Main routine run by gprsd."""
    # Initialize some timestamps and connect to the ConfigDB.
    now = time.time()
    last_scrape_time = now
    last_event_generation_time = now
    last_removal_of_old_data = now
    config_db = ConfigDB()
    while True:
        now = time.time()
        # Get GPRS usage data and store it in the DB.
        if (now - last_scrape_time >
                config_db['gprsd_cli_scrape_period']):
            last_scrape_time = now
            utilities.gather_gprs_data()
        # Generate events for the EventStore with data from the GPRS table.
        if (now - last_event_generation_time >
                config_db['gprsd_event_generation_period']):
            last_event_generation_time = now
            start_time = now - config_db['gprsd_event_generation_period']
            utilities.generate_gprs_events(start_time, now)
        # Clean old records out of the GPRS table.
        if (now - last_removal_of_old_data >
                config_db['gprsd_cleanup_period']):
            last_removal_of_old_data = now
            utilities.clean_old_gprs_records(
                now - config_db['gprsd_max_data_age'])
        # Wait for a bit, then do it again.
        time.sleep(SLEEP_TIME)
