"""Testing GPRS data-scraping, event generation and GPRSDB cleaning.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import os
import time
import unittest

import psycopg2

from core import events
from core.gprs import gprs_database
from core.gprs import utilities
from core.subscriber import subscriber
from core.tests import mocks


# In our CI system, Postgres credentials are stored in env vars.
PG_USER = os.environ.get('PG_USER', 'endaga')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'endaga')


class ScrapeTest(unittest.TestCase):
    """Testing core.gprs.utilities.gather_gprs_data.

    This method should scrape GPRS data via the openbts-python API and it
    should dump this data into the GPRSDB.  We'll mock the scraping return
    values via a monkeypatch to Subscriber.
    """

    @classmethod
    def setUpClass(cls):
        # Monkeypatch Subscriber.
        cls.original_subscriber = utilities.subscriber
        cls.mock_subscriber = mocks.MockSubscriber()
        utilities.subscriber = cls.mock_subscriber
        # Connect to the GPRSDB.
        cls.gprs_db = gprs_database.GPRSDB()

    @classmethod
    def tearDownClass(cls):
        """Repair the monkeypatches."""
        utilities.subscriber = cls.original_subscriber

    def setUp(self):
        """Wipe the GPRSDB before each test."""
        self.gprs_db.empty()

    def test_unknown_imsi(self):
        """If the scraped data contains info for a non-sub, we ignore it."""
        self.mock_subscriber.get_subscriber_return_value = []
        self.mock_subscriber.gprs_return_value = {
            'IMSI901550000000084': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 123,
                'downloaded_bytes': 456,
            },
        }
        utilities.gather_gprs_data()
        # Inspect the records from the GPRSDB.
        records = self.gprs_db.get_records()
        self.assertEqual(0, len(records))

    def test_first_record_for_sub(self):
        """We record scraped data on a registered sub."""
        data = {
            'IMSI000456': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 123,
                'downloaded_bytes': 456,
            },
        }
        self.mock_subscriber.gprs_return_value = data
        utilities.gather_gprs_data()
        # Inspect the records from the GPRSDB.
        records = self.gprs_db.get_records()
        self.assertEqual(1, len(records))
        self.assertEqual('IMSI000456', records[0]['imsi'])
        self.assertEqual('192.168.99.1', records[0]['ipaddr'])
        self.assertEqual(123, records[0]['uploaded_bytes'])
        self.assertEqual(123, records[0]['uploaded_bytes_delta'])
        self.assertEqual(456, records[0]['downloaded_bytes'])
        self.assertEqual(456, records[0]['downloaded_bytes_delta'])

    def test_multiple_records(self):
        """We can record data for multiple registered subs."""
        data = {
            'IMSI000456': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 123,
                'downloaded_bytes': 456,
            },
            'IMSI000667': {
                'ipaddr': '192.168.99.2',
                'uploaded_bytes': 345,
                'downloaded_bytes': 678,
            },
        }
        self.mock_subscriber.gprs_return_value = data
        utilities.gather_gprs_data()
        # Inspect the records from the GPRSDB.
        records = self.gprs_db.get_records()
        self.assertEqual(2, len(records))
        record = self.gprs_db.get_latest_record('IMSI000456')
        self.assertEqual('192.168.99.1', record['ipaddr'])
        self.assertEqual(123, record['uploaded_bytes'])
        self.assertEqual(456, record['downloaded_bytes'])
        self.assertEqual(123, record['uploaded_bytes_delta'])
        self.assertEqual(456, record['downloaded_bytes_delta'])
        record = self.gprs_db.get_latest_record('IMSI000667')
        self.assertEqual('192.168.99.2', record['ipaddr'])
        self.assertEqual(345, record['uploaded_bytes'])
        self.assertEqual(678, record['downloaded_bytes'])
        self.assertEqual(345, record['uploaded_bytes_delta'])
        self.assertEqual(678, record['downloaded_bytes_delta'])

    def test_second_record_for_sub(self):
        """We compute byte deltas correctly."""
        # Simulate results of our first data scrape.
        first_data = {
            'IMSI000432': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 100,
                'downloaded_bytes': 200,
            },
        }
        self.mock_subscriber.gprs_return_value = first_data
        utilities.gather_gprs_data()
        # And the results of our second scrape.
        second_data = {
            'IMSI000432': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 300,
                'downloaded_bytes': 600,
            },
        }
        self.mock_subscriber.gprs_return_value = second_data
        utilities.gather_gprs_data()
        # We should see two records and the second records should have deltas
        # computed correctly.
        records = self.gprs_db.get_records()
        self.assertEqual(2, len(records))
        self.assertEqual(200, records[1]['uploaded_bytes_delta'])
        self.assertEqual(400, records[1]['downloaded_bytes_delta'])

    def test_new_ipaddr(self):
        """We should correctly handle things when the sub gets a new ipaddr.

        If the sub uses GPRS for a bit but then goes idle, OpenBTS may assign
        it a new ipaddr when the sub becomes active again.  When this happens,
        the byte count is reset, so our deltas should take that into account.
        """
        # Simulate results of our first data scrape.
        first_data = {
            'IMSI000321': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 100,
                'downloaded_bytes': 200,
            },
        }
        self.mock_subscriber.gprs_return_value = first_data
        utilities.gather_gprs_data()
        # And the results of our second scrape (new ipaddr).
        second_data = {
            'IMSI000321': {
                'ipaddr': '192.168.99.10',
                'uploaded_bytes': 300,
                'downloaded_bytes': 600,
            },
        }
        self.mock_subscriber.gprs_return_value = second_data
        utilities.gather_gprs_data()
        # We should see two records and the second records should have deltas
        # computed correctly.
        records = self.gprs_db.get_records()
        self.assertEqual(2, len(records))
        self.assertEqual(300, records[1]['uploaded_bytes_delta'])
        self.assertEqual(600, records[1]['downloaded_bytes_delta'])

    def test_reassigned_ipaddr(self):
        """Compute deltas correctly when byte count resets.

        If the sub uses GPRS for a bit but then goes idle, OpenBTS may assign
        it a new ipaddr when the sub becomes active again.  If OpenBTS happens
        to assign the same IP address as before, the byte count will still be
        reset and will likely be less than the last measurement before the sub
        went idle.  So, in this case, when the byte count is lower than the
        previous measurement, we compute the delta by using a starting value of
        zero.
        """
        # Simulate results of our first data scrape.
        first_data = {
            'IMSI000765': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 1000,
                'downloaded_bytes': 2000,
            },
        }
        self.mock_subscriber.gprs_return_value = first_data
        utilities.gather_gprs_data()
        # And the results of our second scrape (same ipaddr but the byte counts
        # are lower than before, suggesting a reset of the counts).
        second_data = {
            'IMSI000765': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 200,
                'downloaded_bytes': 400,
            },
        }
        self.mock_subscriber.gprs_return_value = second_data
        utilities.gather_gprs_data()
        # We should see two records and the second records should have deltas
        # computed correctly.
        records = self.gprs_db.get_records()
        self.assertEqual(2, len(records))
        self.assertEqual(200, records[1]['uploaded_bytes_delta'])
        self.assertEqual(400, records[1]['downloaded_bytes_delta'])

    def test_add_record_sans_timestamp(self):
        """The current timestamp can be added automatically."""
        imsi = 'IMSI901550000000084'
        now = time.time()
        self.gprs_db.add_record(imsi, '192.168.99.4', 20, 10, 5, 2)
        record = self.gprs_db.get_latest_record(imsi)
        timestamp = int(record['record_timestamp'].strftime('%s'))
        self.assertLessEqual(abs(now - timestamp), 5)

    def test_unchanged_measurements(self):
        """Simulate an IMSI with no activity between measurements.

        In old versions this caused an error where byte deltas were measured
        from zero.
        """
        # Simulate results of our first data scrape.
        first_data = {
            'IMSI000432': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 100,
                'downloaded_bytes': 200,
            },
        }
        self.mock_subscriber.gprs_return_value = first_data
        utilities.gather_gprs_data()
        # And the results of our second scrape (the data is unchanged).
        second_data = {
            'IMSI000432': {
                'ipaddr': '192.168.99.1',
                'uploaded_bytes': 100,
                'downloaded_bytes': 200,
            },
        }
        self.mock_subscriber.gprs_return_value = second_data
        utilities.gather_gprs_data()
        # We should see two records and the second records should have deltas
        # computed correctly.
        records = self.gprs_db.get_records()
        self.assertEqual(2, len(records))
        self.assertEqual(0, records[1]['uploaded_bytes_delta'])
        self.assertEqual(0, records[1]['downloaded_bytes_delta'])


class EventGenerationTest(unittest.TestCase):
    """Testing core.gprs.generate_gprs_events."""

    @classmethod
    def setUpClass(cls):
        # Monkeypatch Subscriber so sub balance lookups succeed.
        cls.original_subscriber = utilities.subscriber
        cls.mock_subscriber = mocks.MockSubscriber()
        utilities.subscriber = cls.mock_subscriber
        subscriber.create_subscriber('IMSI901550000000084', '5551234')
        subscriber.create_subscriber('IMSI901550000000082', '5551235')
        # Connect to the GPRSDB and EventStore.
        cls.gprs_db = gprs_database.GPRSDB()
        cls.event_store = events.EventStore()
        # Add some records to the GPRSDB.  The method we're testing should
        # extract these records and create events in the EventStore.
        cls.now = time.time()
        records = [
            (psycopg2.TimestampFromTicks(cls.now - 120), 'IMSI901550000000084',
             '192.168.99.1', 50, 80, 50, 80),
            (psycopg2.TimestampFromTicks(cls.now - 60), 'IMSI901550000000084',
             '192.168.99.1', 50, 80, 0, 0),
            (psycopg2.TimestampFromTicks(cls.now - 30), 'IMSI901550000000084',
             '192.168.99.1', 300, 500, 250, 420),
            (psycopg2.TimestampFromTicks(cls.now - 10), 'IMSI901550000000084',
             '192.168.99.1', 700, 600, 400, 100),
            (psycopg2.TimestampFromTicks(cls.now - 5), 'IMSI901550000000084',
             '192.168.99.1', 750, 625, 50, 25),
            # Create events for a different IMSI.
            (psycopg2.TimestampFromTicks(cls.now - 60), 'IMSI901550000000082',
             '192.168.99.2', 50, 80, 0, 0),
            (psycopg2.TimestampFromTicks(cls.now - 10), 'IMSI901550000000082',
             '192.168.99.2', 400, 300, 350, 220),
            (psycopg2.TimestampFromTicks(cls.now - 5), 'IMSI901550000000082',
             '192.168.99.2', 450, 325, 50, 25),
        ]
        schema = ('record_timestamp, imsi, ipaddr, uploaded_bytes,'
                  ' downloaded_bytes, uploaded_bytes_delta,'
                  ' downloaded_bytes_delta')
        connection = psycopg2.connect(host='localhost', database='endaga',
                                      user=PG_USER, password=PG_PASSWORD)
        with connection.cursor() as cursor:
            for record in records:
                values = "%s, '%s', '%s', %s, %s, %s, %s" % record
                command = 'insert into gprs_records (%s) values(%s)' % (
                    schema, values)
                cursor.execute(command)
        connection.commit()

    @classmethod
    def tearDownClass(cls):
        # Repair the monkeypatch.
        utilities.subscriber = cls.original_subscriber
        subscriber.delete_subscriber('IMSI901550000000084')
        subscriber.delete_subscriber('IMSI901550000000082')
        # Clear the GPRSDB.
        cls.gprs_db.empty()

    def setUp(self):
        """Wipe the EventStore before each test."""
        self.event_store.drop_table()

    def test_capture_events_in_interval(self):
        """We can get events in an interval."""
        delta_t = 30
        utilities.generate_gprs_events(self.now - delta_t, self.now)
        generated_events = self.event_store.get_events()
        self.assertEqual(2, len(generated_events))
        imsis = ['IMSI901550000000084', 'IMSI901550000000082']
        self.assertItemsEqual(imsis, [e['imsi'] for e in generated_events])
        self.assertEqual(700 + 400,
                         sum([e['up_bytes'] for e in generated_events]))
        self.assertEqual(545 + 245,
                         sum([e['down_bytes'] for e in generated_events]))
        for event in generated_events:
            # The subscriber's balance should be unchanged as data usage is
            # free at the moment.
            self.assertEqual(event['oldamt'], event['newamt'])
            self.assertEqual('gprs', event['kind'])
            self.assertEqual(delta_t, event['timespan'])

    def test_capture_events_in_longer_interval(self):
        """We can get events in an interval.

        We should also not create events when the byte deltas are both zero.
        """
        delta_t = 150
        utilities.generate_gprs_events(self.now - delta_t, self.now)
        generated_events = self.event_store.get_events()
        # We should get all the events except for the one where the byte deltas
        # are zero.
        self.assertEqual(2, len(generated_events))
        self.assertEqual(750 + 400,
                         sum([e['up_bytes'] for e in generated_events]))


class CleanupTest(unittest.TestCase):
    """"Testing core.gprs.clean_old_gprs_records."""

    def setUp(self):
        # Connect to the GPRSDB.
        self.gprs_db = gprs_database.GPRSDB()
        # Add some records to the GPRSDB.
        self.now = time.time()
        records = [
            (psycopg2.TimestampFromTicks(self.now - 60), 'IMSI901550000000084',
             '192.168.99.1', 100, 200, 100, 200),
            (psycopg2.TimestampFromTicks(self.now - 30), 'IMSI901550000000084',
             '192.168.99.1', 300, 500, 200, 300),
            (psycopg2.TimestampFromTicks(self.now - 10), 'IMSI901550000000084',
             '192.168.99.1', 700, 600, 400, 100),
            (psycopg2.TimestampFromTicks(self.now - 5), 'IMSI901550000000084',
             '192.168.99.1', 750, 625, 50, 25),
        ]
        schema = ('record_timestamp, imsi, ipaddr, uploaded_bytes,'
                  ' downloaded_bytes, uploaded_bytes_delta,'
                  ' downloaded_bytes_delta')
        connection = psycopg2.connect(host='localhost', database='endaga',
                                      user=PG_USER, password=PG_PASSWORD)
        with connection.cursor() as cursor:
            for record in records:
                values = "%s, '%s', '%s', %s, %s, %s, %s" % record
                command = 'insert into gprs_records (%s) values(%s)' % (
                    schema, values)
                cursor.execute(command)
        connection.commit()

    def tearDown(self):
        # Clear the GPRSDB.
        self.gprs_db.empty()

    def test_very_old_records(self):
        """So old that no events should be dropped."""
        utilities.clean_old_gprs_records(self.now - 300)
        records = self.gprs_db.get_records()
        self.assertEqual(4, len(records))

    def test_semi_recent_records(self):
        """Delete some new-ish records."""
        utilities.clean_old_gprs_records(self.now - 30)
        records = self.gprs_db.get_records()
        # The 30-second old record actually stays around because we delete
        # records that are strictly older than the specified timestamp, not 'as
        # old or older,' just 'older.'
        self.assertEqual(3, len(records))

    def test_very_recent_records(self):
        """Delete it all."""
        utilities.clean_old_gprs_records(self.now - 1)
        records = self.gprs_db.get_records()
        self.assertEqual(0, len(records))
