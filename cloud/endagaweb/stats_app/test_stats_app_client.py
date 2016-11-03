"""Testing the stats_app clients.

usage:
    $ python manage.py test
    $ python manage.py test endagaweb
    $ python manage.py test endagaweb.StatsClientTest
    $ python manage.py test endagaweb.StatsClientTest.test_one_thing_eg

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import calendar
from datetime import datetime
from datetime import timedelta

from django.test import TestCase
import pytz

from endagaweb import models
from endagaweb.stats_app import stats_client


# We generate a lot of UsageEvents in these tests.  This date will be the date
# of the most recent events.  We fix it here rather than using something like
# datetime.today because the latter breaks some of the aggregation tests that
# depend on the date and certain intervals.
DATE = datetime.strptime('Jan 30 2015, 8:15 AM', '%b %d %Y, %H:%M %p')
TIME_OF_LAST_EVENT = DATE.replace(tzinfo=pytz.UTC)
# We also set fixed values for billsec, uploaded bytes, downloaded bytes and
# the gprs timespan to make the testing math easier.
BILLSEC = 10
UPLOADED_BYTES = 10
DOWNLOADED_BYTES = 100
GPRS_TIMESPAN = 60


def _add_usage_events(subscriber, bts, kind, num_events):
    """Add a number of UsageEvents.

    Starts adding at TIME_OF_LAST_EVENT and adds an event for each hour
    preceding.  Also tries to make the account charges and balance changes
    realistic.

    Args:
        subscriber: a models.Subscriber
        bts: a models.BTS
        kind: a value for models.UsageEvent.kind
        num_events: the number of Usage events to add with these params.
    """
    old_balance, cost = 1000, 10
    hours, time_delta = 0, 1
    # Set the billsec to a fixed number if we're adding a call UE.
    call_kinds = ['outside_call', 'incoming_call', 'local_call',
                  'local_recv_call', 'free_call', 'error_call']
    if kind in call_kinds:
        billsec = BILLSEC
    else:
        billsec = None
    # Set the byte counts if we're adding a GPRS UE.
    if kind == 'gprs':
        up_bytes = UPLOADED_BYTES
        down_bytes = DOWNLOADED_BYTES
        gprs_timespan = GPRS_TIMESPAN
    else:
        up_bytes = None
        down_bytes = None
        gprs_timespan = None
    for _ in range(num_events):
        date = TIME_OF_LAST_EVENT - timedelta(hours=hours)
        new_balance = old_balance - cost
        event = models.UsageEvent(
            subscriber=subscriber, bts=bts, date=date, kind=kind,
            reason='test reason', oldamt=old_balance, newamt=new_balance,
            change=cost, billsec=billsec, uploaded_bytes=up_bytes,
            downloaded_bytes=down_bytes, timespan=gprs_timespan)
        event.save()
        old_balance = new_balance
        hours += time_delta


class StatsClientTest(TestCase):
    """Testing SMS and call stats clients."""

    @classmethod
    def setUpClass(cls):
        """Add some test data."""
        # Setup a User and UserProfile.
        user = models.User(username="xi", email="xi@endaga.com")
        user.set_password("testpw")
        user.save()
        user_profile = models.UserProfile.objects.get(user=user)
        # Setup two Networks.
        cls.network_a = models.Network(name='network-a')
        cls.network_a.save()
        cls.network_b = models.Network(name='network-b')
        cls.network_b.save()
        # Setup two BTS on different networks with the same user.
        bts_one = models.BTS(uuid='59216199-d664-4b7a-a2db-6f26e9a5d204',
                             nickname='tower-nickname-100',
                             inbound_url='http://localhost:8090',
                             network=cls.network_a)
        bts_one.save()
        bts_two = models.BTS(uuid='59216199-d664-4b7a-a2db-6f26e9a5d205',
                             nickname='tower-nickname-200',
                             inbound_url='http://localhost:8090',
                             network=cls.network_b)
        bts_two.save()
        # Add two Subscribers.
        subscriber_a = models.Subscriber(
            network=bts_one.network, imsi='IMSI999990000000000',
            name='subscriber a', balance=10000, state='active')
        subscriber_a.save()
        subscriber_b = models.Subscriber(
            network=bts_two.network, imsi='IMSI999990000000001',
            name='subscriber b', balance=20000, state='active')
        subscriber_b.save()
        # Add some UsageEvents for the BTS and Subscribers.
        cls.number_of_outside_sms_bts_one = 10
        cls.number_of_local_sms_bts_two = 20
        cls.number_of_outside_calls_bts_one = 30
        cls.number_of_local_calls_bts_two = 40
        cls.number_of_gprs_events_bts_one = 50
        cls.number_of_gprs_events_bts_two = 60
        _add_usage_events(subscriber_a, bts_one, 'outside_sms',
                          cls.number_of_outside_sms_bts_one)
        _add_usage_events(subscriber_b, bts_two, 'local_sms',
                          cls.number_of_local_sms_bts_two)
        _add_usage_events(subscriber_a, bts_one, 'outside_call',
                          cls.number_of_outside_calls_bts_one)
        _add_usage_events(subscriber_b, bts_two, 'local_call',
                          cls.number_of_local_calls_bts_two)
        _add_usage_events(subscriber_a, bts_one, 'gprs',
                          cls.number_of_gprs_events_bts_one)
        _add_usage_events(subscriber_b, bts_two, 'gprs',
                          cls.number_of_gprs_events_bts_two)
        # Keep references to these objects so we can destroy them later.
        # TODO(matt): also grab all the usage_events that are generated.
        cls.objects = [user, user_profile, cls.network_a, cls.network_b,
                       bts_one, bts_two, subscriber_a, subscriber_b]

    @classmethod
    def tearDownClass(cls):
        """Delete the test data."""
        for object_instance in cls.objects:
            object_instance.delete()

    def test_get_global_sms_timeseries(self):
        """We can get a timeseries of SMS data with SMS client."""
        level = 'global'
        sms_stats_client = stats_client.SMSStatsClient(level)
        data = sms_stats_client.timeseries()
        # The timeseries method returns a list and the last value should be
        # (millisecond timestamp, <total number of SMS UsageEvents>).  Since we
        # haven't specified a timespan or a kind, the client will return all of
        # the data.
        timestamp, _ = data[-1]
        self.assertTrue(isinstance(timestamp, int))
        sms_count = sum(zip(*data)[1])
        expected_number_of_sms = (self.number_of_outside_sms_bts_one +
                                  self.number_of_local_sms_bts_two)
        self.assertEqual(expected_number_of_sms, sms_count)

    def test_get_network_sms_timeseries(self):
        """We can get timeseries SMS stats for a specific network."""
        level = 'network'
        level_id = self.network_a.id
        sms_stats_client = stats_client.SMSStatsClient(level,
                                                       level_id=level_id)
        data = sms_stats_client.timeseries()
        network_sms_count = sum(zip(*data)[1])
        # Only BTS one is on Network A so we should only see that BTS's events.
        self.assertEqual(self.number_of_outside_sms_bts_one, network_sms_count)

    def test_get_specific_sms_kind(self):
        """We can get timeseries SMS data of a specific kind."""
        level = 'global'
        kind = 'local_sms'
        sms_stats_client = stats_client.SMSStatsClient(level)
        data = sms_stats_client.timeseries(kind=kind)
        local_sms_count = sum(zip(*data)[1])
        self.assertEqual(self.number_of_local_sms_bts_two, local_sms_count)

    def test_get_all_sms(self):
        """We can get all timeseries SMS data by specifying the 'sms' kind or
        by relying on the defaults.
        """
        level = 'global'
        sms_stats_client = stats_client.SMSStatsClient(level)
        kind = 'sms'
        data = sms_stats_client.timeseries(kind=kind)
        expected_number_of_sms = (self.number_of_outside_sms_bts_one +
                                  self.number_of_local_sms_bts_two)
        global_sms_count = sum(zip(*data)[1])
        self.assertEqual(expected_number_of_sms, global_sms_count)
        # We expect this to also default to the 'sms' (all) kind.
        data = sms_stats_client.timeseries()
        global_sms_count = sum(zip(*data)[1])
        self.assertEqual(expected_number_of_sms, global_sms_count)

    def test_get_sms_with_date_range_and_interval(self):
        """We can specify a date range and interval."""
        level = 'global'
        sms_stats_client = stats_client.SMSStatsClient(level)
        # Setup client params, converting datetimes to timestamps.
        start_datetime = TIME_OF_LAST_EVENT - timedelta(hours=36)
        start_timestamp = calendar.timegm(start_datetime.utctimetuple())
        end_timestamp = calendar.timegm(TIME_OF_LAST_EVENT.utctimetuple())
        data = sms_stats_client.timeseries(start_time_epoch=start_timestamp,
                                           end_time_epoch=end_timestamp,
                                           interval='days')
        days, values = zip(*data)
        # The interval comes back from qsstats with an extra day at the
        # beginning.
        expected_datetimes = [TIME_OF_LAST_EVENT - timedelta(hours=48),
                              TIME_OF_LAST_EVENT - timedelta(hours=24),
                              TIME_OF_LAST_EVENT]
        # TIME_OF_LAST_EVENT has hour/minute info -- we need to clear that out
        # because the qsstats datetimes are, in this example, days only.
        expected_days = [dt.replace(hour=0, minute=0) for dt in
                         expected_datetimes]
        # And finally we have to convert these to millisecond timestamps.
        expected_timestamps = [int(1e3 * calendar.timegm(dt.utctimetuple()))
                               for dt in expected_days]
        self.assertSequenceEqual(expected_timestamps, days)
        # We expect 30 total SMS to be sent and we can work out how they will
        # accumulate day-to-day by knowing that we added one usage event of
        # each type per hour, counting back from 8:15a (see _add_usage_events
        # for the timings).
        expected_values = [0, 12, 18]
        self.assertSequenceEqual(expected_values, values)

    def test_get_global_call_timeseries(self):
        """We can get a timeseries of call count data with the call client."""
        level = 'global'
        call_stats_client = stats_client.CallStatsClient(level)
        data = call_stats_client.timeseries()
        # The timeseries method returns a list and the last value should be
        # (millisecond timestamp, <total number of call UsageEvents>).  Since
        # we haven't specified a timespan or a kind, the client will return all
        # of the data.
        timestamp, _ = data[-1]
        self.assertTrue(isinstance(timestamp, int))
        call_count = sum(zip(*data)[1])
        expected_number_of_calls = (self.number_of_outside_calls_bts_one +
                                    self.number_of_local_calls_bts_two)
        self.assertEqual(expected_number_of_calls, call_count)

    def test_get_network_call_timeseries(self):
        """We can get timeseries call stats for a specific network."""
        level = 'network'
        level_id = self.network_a.id
        call_stats_client = stats_client.CallStatsClient(level,
                                                         level_id=level_id)
        data = call_stats_client.timeseries()
        network_call_count = sum(zip(*data)[1])
        # Only BTS one is on Network A so we should only see that BTS's events.
        self.assertEqual(self.number_of_outside_calls_bts_one,
                         network_call_count)

    def test_get_specific_call_kind(self):
        """We can get timeseries call data of a specific kind."""
        level = 'global'
        kind = 'local_call'
        call_stats_client = stats_client.CallStatsClient(level)
        data = call_stats_client.timeseries(kind=kind)
        local_call_count = sum(zip(*data)[1])
        self.assertEqual(self.number_of_local_calls_bts_two, local_call_count)

    def test_get_call_with_date_range_and_interval(self):
        """We can specify a date range and interval for call data."""
        level = 'global'
        call_stats_client = stats_client.CallStatsClient(level)
        # Setup client params, converting datetimes to timestamps.
        start_datetime = TIME_OF_LAST_EVENT - timedelta(hours=96)
        start_timestamp = calendar.timegm(start_datetime.utctimetuple())
        end_timestamp = calendar.timegm(TIME_OF_LAST_EVENT.utctimetuple())
        data = call_stats_client.timeseries(start_time_epoch=start_timestamp,
                                            end_time_epoch=end_timestamp,
                                            interval='days')
        days, values = zip(*data)
        # The interval comes back from qsstats with an extra day at the
        # beginning.
        expected_datetimes = [TIME_OF_LAST_EVENT - timedelta(hours=96),
                              TIME_OF_LAST_EVENT - timedelta(hours=72),
                              TIME_OF_LAST_EVENT - timedelta(hours=48),
                              TIME_OF_LAST_EVENT - timedelta(hours=24),
                              TIME_OF_LAST_EVENT]
        # TIME_OF_LAST_EVENT has hour/minute info -- we need to clear that out
        # because the qsstats datetimes are, in this example, days only.
        expected_days = [dt.replace(hour=0, minute=0) for dt in
                         expected_datetimes]
        # And finally we have to convert these to millisecond timestamps.
        expected_timestamps = [int(1e3 * calendar.timegm(dt.utctimetuple()))
                               for dt in expected_days]
        self.assertSequenceEqual(expected_timestamps, days)
        # We expect 70 total calls to be sent and we can work out how they will
        # accumulate day-to-day by knowing that we added one usage event of
        # each type per hour, counting back from 8:15a (see _add_usage_events
        # for the timings).
        expected_values = [0+0, 0+0, 0+7, 21+24, 9+9]
        self.assertSequenceEqual(expected_values, values)

    def test_global_billsec_timeseries(self):
        """We can get a timeseries of billsec data."""
        level = 'global'
        call_stats_client = stats_client.CallStatsClient(level)
        data = call_stats_client.timeseries(aggregation='duration')
        # The timeseries method returns a list and the last value should be
        # (millisecond timestamp, <duration of call UsageEvents>).  Since we
        # haven't specified a timespan or a kind, the client will return all
        # of the data.  We can do some initial checks on the types and the sum
        # of these values.
        timestamp, _ = data[-1]
        self.assertTrue(isinstance(timestamp, int))
        total_duration = sum(zip(*data)[1])
        expected_duration = (
            BILLSEC * self.number_of_outside_calls_bts_one +
            BILLSEC * self.number_of_local_calls_bts_two)
        self.assertEqual(expected_duration, total_duration)

    def test_get_network_billsec_timeseries(self):
        """We can get timeseries billsec stats for a specific network."""
        level = 'network'
        level_id = self.network_a.id
        call_stats_client = stats_client.CallStatsClient(level,
                                                         level_id=level_id)
        data = call_stats_client.timeseries(aggregation='duration')
        network_duration = sum(zip(*data)[1])
        # Only BTS one is on Network A so we should only see that BTS's events.
        expected_duration = (
            BILLSEC * self.number_of_outside_calls_bts_one)
        self.assertEqual(expected_duration, network_duration)

    def test_get_specific_call_kind_duration(self):
        """We can get timeseries billsec data of a specific kind."""
        level = 'global'
        kind = 'local_call'
        call_stats_client = stats_client.CallStatsClient(level)
        data = call_stats_client.timeseries(kind=kind, aggregation='duration')
        local_billsec = sum(zip(*data)[1])
        expected_duration = BILLSEC * self.number_of_local_calls_bts_two
        self.assertEqual(expected_duration, local_billsec)

    def test_get_global_gprs_timeseries(self):
        """We can get a timeseries of GPRS data with GPRS client."""
        level = 'global'
        gprs_stats_client = stats_client.GPRSStatsClient(level)
        data = gprs_stats_client.timeseries()
        # The timeseries method returns a list and the last value should be
        # (millisecond timestamp, <total amount of data used>).  Since we
        # haven't specified a timespan or a kind, the client will return all of
        # the data.
        timestamp, _ = data[-1]
        self.assertTrue(isinstance(timestamp, int))
        data_sum = sum(zip(*data)[1])
        expected_data_total = (
            UPLOADED_BYTES * self.number_of_gprs_events_bts_one +
            DOWNLOADED_BYTES * self.number_of_gprs_events_bts_one +
            UPLOADED_BYTES * self.number_of_gprs_events_bts_two +
            DOWNLOADED_BYTES * self.number_of_gprs_events_bts_two
        )
        # Convert the data to MB.
        expected_data_total = expected_data_total / 2.**20
        self.assertEqual(expected_data_total, data_sum)

    def test_get_network_gprs_timeseries(self):
        """We can get timeseries GPRS stats for a specific network."""
        level = 'network'
        level_id = self.network_a.id
        gprs_stats_client = stats_client.GPRSStatsClient(level,
                                                         level_id=level_id)
        data = gprs_stats_client.timeseries()
        data_sum = sum(zip(*data)[1])
        # Only BTS one is on Network A so we should only see that BTS's events.
        expected_data_total = (
            UPLOADED_BYTES * self.number_of_gprs_events_bts_one +
            DOWNLOADED_BYTES * self.number_of_gprs_events_bts_one
        )
        # Convert the data to MB.
        expected_data_total = expected_data_total / 2.**20
        self.assertEqual(expected_data_total, data_sum)

    def test_get_gprs_uploaded_data(self):
        """We can get timeseries GPRS uploaded byte data."""
        level = 'global'
        kind = 'uploaded_data'
        gprs_stats_client = stats_client.GPRSStatsClient(level)
        data = gprs_stats_client.timeseries(kind=kind)
        data_sum = sum(zip(*data)[1])
        expected_data_total = (
            UPLOADED_BYTES * self.number_of_gprs_events_bts_one +
            UPLOADED_BYTES * self.number_of_gprs_events_bts_two
        )
        # Convert the data to MB.
        expected_data_total = expected_data_total / 2.**20
        self.assertEqual(expected_data_total, data_sum)

    def test_get_gprs_downloaded_data(self):
        """We can get timeseries GPRS downloaded byte data."""
        level = 'global'
        kind = 'downloaded_data'
        gprs_stats_client = stats_client.GPRSStatsClient(level)
        data = gprs_stats_client.timeseries(kind=kind)
        data_sum = sum(zip(*data)[1])
        expected_data_total = (
            DOWNLOADED_BYTES * self.number_of_gprs_events_bts_one +
            DOWNLOADED_BYTES * self.number_of_gprs_events_bts_two
        )
        # Convert the data to MB.
        expected_data_total = expected_data_total / 2.**20
        self.assertEqual(expected_data_total, data_sum)

    def test_get_gprs_with_date_range_and_interval(self):
        """We can specify a date range and interval."""
        level = 'global'
        gprs_stats_client = stats_client.GPRSStatsClient(level)
        # Setup client params, converting datetimes to timestamps.
        start_datetime = TIME_OF_LAST_EVENT - timedelta(hours=96)
        start_timestamp = calendar.timegm(start_datetime.utctimetuple())
        end_timestamp = calendar.timegm(TIME_OF_LAST_EVENT.utctimetuple())
        data = gprs_stats_client.timeseries(start_time_epoch=start_timestamp,
                                            end_time_epoch=end_timestamp,
                                            interval='days')
        days, values = zip(*data)
        # The interval comes back from qsstats with an extra day at the
        # beginning.
        expected_datetimes = [TIME_OF_LAST_EVENT - timedelta(hours=96),
                              TIME_OF_LAST_EVENT - timedelta(hours=72),
                              TIME_OF_LAST_EVENT - timedelta(hours=48),
                              TIME_OF_LAST_EVENT - timedelta(hours=24),
                              TIME_OF_LAST_EVENT]
        # TIME_OF_LAST_EVENT has hour/minute info -- we need to clear that out
        # because the qsstats datetimes are, in this example, days only.
        expected_days = [dt.replace(hour=0, minute=0) for dt in
                         expected_datetimes]
        # And finally we have to convert these to millisecond timestamps.
        expected_timestamps = [int(1e3 * calendar.timegm(dt.utctimetuple()))
                               for dt in expected_days]
        self.assertSequenceEqual(expected_timestamps, days)
        # We expect 110 total GPRS events to be created and we can work out how
        # they will accumulate day-to-day by knowing that we added one usage
        # event of each type per hour, counting back from 8:15a (see
        # _add_usage_events for the timings).
        expected_event_counts = [0+0, 0+3, 17+24, 24+24, 9+9]
        bytes_per_event = UPLOADED_BYTES + DOWNLOADED_BYTES
        expected_values = [bytes_per_event * i for i in expected_event_counts]
        # Convert the data to MB.
        expected_values = [e / 2.**20 for e in expected_values]
        self.assertSequenceEqual(expected_values, values)


class TowerStatsTest(TestCase):
    """Testing stats derived from TimeseriesStats instances."""

    @classmethod
    def setUpClass(cls):
        """Add some test data."""
        # Setup a User and UserProfile.
        user = models.User(username="xi", email="xi@endaga.com")
        user.set_password("testpw")
        user.save()
        user_profile = models.UserProfile.objects.get(user=user)
        # Setup two BTS on different networks with the same user.
        cls.bts = models.BTS(uuid='59216199-d664-4b7a-a2db-6f26e9a5d204',
                             nickname='tower-nickname-100',
                             inbound_url='http://localhost:8090',
                             network=user_profile.network)
        cls.bts.save()
        # Add some TimeseriesStats.
        cls.start_date = datetime.strptime('Jul 9 2015, 8:15 AM',
                                           '%b %d %Y, %H:%M %p')
        increment = timedelta(hours=12)
        stat_values = [
            (cls.start_date + 0 * increment, 'tchf_load', 4),
            (cls.start_date + 1 * increment, 'tchf_load', 6),
            (cls.start_date + 2 * increment, 'tchf_load', 2),
            (cls.start_date + 3 * increment, 'tchf_load', 7),
            (cls.start_date + 4 * increment, 'tchf_load', 9),
        ]
        for date, key, value in stat_values:
            stat = models.TimeseriesStat(
                date=date, key=key, value=value, bts=cls.bts,
                network=user_profile.network)
            stat.save()
        # Keep references to these objects so we can destroy them later.
        cls.objects = [user, user_profile, cls.bts]

    @classmethod
    def tearDownClass(cls):
        """Delete the test data."""
        for object_instance in cls.objects:
            object_instance.delete()

    def test_day_interval(self):
        """We can get data in day intervals."""
        level = 'tower'
        timeseries_stats_client = stats_client.TimeseriesStatsClient(
            level, level_id=self.bts.id)
        # Setup client params, converting datetimes to timestamps.
        start_timestamp = calendar.timegm(self.start_date.utctimetuple())
        end_datetime = self.start_date + 4 * timedelta(hours=12)
        end_timestamp = calendar.timegm(end_datetime.utctimetuple())
        data = timeseries_stats_client.timeseries(
            start_time_epoch=start_timestamp, end_time_epoch=end_timestamp,
            interval='days', key='tchf_load')
        days, values = zip(*data)
        expected_datetimes = [self.start_date,
                              self.start_date + timedelta(days=1),
                              self.start_date + timedelta(days=2)]
        # cls.start_date has hour/minute info -- we need to clear that out
        # because the qsstats datetimes are, in this example, days only.
        expected_days = [dt.replace(hour=0, minute=0) for dt in
                         expected_datetimes]
        # And finally we have to convert these to millisecond timestamps.
        expected_timestamps = [int(1e3 * calendar.timegm(dt.utctimetuple()))
                               for dt in expected_days]
        self.assertSequenceEqual(expected_timestamps, days)
        # We can compute the expected averages manually.
        expected_values = (5, 4.5, 9)
        self.assertSequenceEqual(expected_values, values)

    def test_week_interval(self):
        """We can get data in week intervals."""
        level = 'tower'
        timeseries_stats_client = stats_client.TimeseriesStatsClient(
            level, level_id=self.bts.id)
        # Setup client params, converting datetimes to timestamps.
        start_timestamp = calendar.timegm(self.start_date.utctimetuple())
        end_datetime = self.start_date + timedelta(days=5)
        end_timestamp = calendar.timegm(end_datetime.utctimetuple())
        data = timeseries_stats_client.timeseries(
            start_time_epoch=start_timestamp, end_time_epoch=end_timestamp,
            interval='weeks', key='tchf_load')
        days, values = zip(*data)
        # We can compute the expected averages manually.
        expected_values = [(4 + 6 + 2 + 7 + 9) / 5., 0]
        self.assertSequenceEqual(expected_values, values)
