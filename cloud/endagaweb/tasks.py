"""Celery task definitions.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import

import csv
import datetime
import json
import time
import os
import paramiko
import zipfile
try:
    # we only import zlib here to check that it is available
    # (why would it not be?), so we have to disable the 'unused' warning
    import zlib  # noqa: F401
    zip_compression = zipfile.ZIP_DEFLATED
except:
    zip_compression = zipfile.ZIP_STORED


from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db.models import Avg, Count
import django.utils.timezone
import requests

from endagaweb.celery import app
from endagaweb.models import BTS
from endagaweb.models import Network
from endagaweb.models import PendingCreditUpdate
from endagaweb.models import ConfigurationKey
from endagaweb.models import Subscriber
from endagaweb.models import UsageEvent
from endagaweb.models import SystemEvent
from endagaweb.models import TimeseriesStat
from endagaweb.ic_providers.nexmo import NexmoProvider


@app.task(bind=True)
def usageevents_to_sftp(self):
    """Gets all usage events from the endagaweb_usageevent table
    Writes the data to a CSV file
    Transfers the CSV file to an sftp account
    """
    all_usageevents = UsageEvent.objects.all().iterator()

    headers = [
        'Transaction ID',
        'Date',
        'Subscriber IMSI',
        'BTS Identifier',
        'Type of Event',
        'Description',
        'Old Amount',
        'New Amount',
        'Change',
        'Billable Call Duration (sec)',
        'Total Call Duration (sec)',
        'From IMSI',
        'From Number',
        'To IMSI',
        'To Number',
        'Tariff',
        'Bytes Uploaded',
        'Bytes Downloaded',
        'Timespan',
        'Date Synced',
    ]

    local_path = "/tmp/"
    destination_path = 'TIP/data/'
    now = datetime.datetime.now().date()
    usageevent_data_file = "usageevent_%s.csv" % (now, )
    zip_file = "usageevent_%s.zip" % (now, )

    writer = csv.writer(open(local_path + usageevent_data_file, 'wb'))
    writer.writerow(headers)
    for e in all_usageevents:
        try:
            #first strip the IMSI off if present
            subscriber = e.subscriber_imsi
            if e.subscriber_imsi.startswith('IMSI'):
                subscriber = e.subscriber_imsi[4:]

            writer.writerow([
                        e.transaction_id,
                        e.date,
                        subscriber,
                        e.bts_uuid,
                        e.kind,
                        e.reason,
                        e.oldamt,
                        e.newamt,
                        e.change,
                        e.billsec,
                        e.call_duration,
                        e.from_imsi,
                        e.from_number,
                        e.to_imsi,
                        e.to_number,
                        e.tariff,
                        e.uploaded_bytes,
                        e.downloaded_bytes,
                        e.timespan,
                        e.date_synced,
                        ])
        except AttributeError:
            print "Failure: %s" % e
            continue

    with zipfile.ZipFile(local_path + zip_file, mode='w') as zipf:
        zipf.write(local_path + usageevent_data_file,
                   compress_type=zip_compression)
        # if we successfully wrote the CSV file into the ZIP archive we can
        # now delete the CSV file.
        os.remove(local_path + usageevent_data_file)

    host = settings.SFTP['SFTP_HOST']
    username = settings.SFTP['SFTP_USERNAME']
    password = settings.SFTP['SFTP_PASSWORD']
    transport = paramiko.Transport(host)
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    sftp.put(local_path + zip_file, destination_path + zip_file, confirm=True)
    transport.close()
    # no exception raised: assume ZIP successfully transferred and delete
    # it (can always be recreated).
    os.remove(local_path + zip_file)


@app.task(bind=True)
def async_post(self, url, data, retry_delay=60*10, max_retries=432):
    """Tries to send a POST request to an endpoint with some data.

    The default retry is every 10 min for 3 days.
    """
    print "attempting to send POST request to endpoint '%s'" % url
    try:
        r = requests.post(url, data=data,
                          timeout=settings.ENDAGA['BTS_REQUEST_TIMEOUT_SECS'])
        if r.status_code >= 200 and r.status_code < 300:
            print "async_post SUCCESS. url: '%s' (%d). Response was: %s" % (
                r.url, r.status_code, r.text)
            return r.status_code
        else:
            print "async_post FAIL. url: '%s' (%d). Response was: %s" % (
                r.url, r.status_code, r.text)
            raise ValueError(r.status_code)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise self.retry(countdown=retry_delay, max_retries=max_retries)
    except Exception as exception:
        print "async_post ERROR. url: '%s' exception: %s" % (url, exception)
        raise


@app.task(bind=True)
def async_get(self, url, params, retry_delay=60*10, max_retries=432):
    # default retry is every 10 min for 3 days
    print "attempting to send GET request to '%s' w/ params '%s'" % (url, params)
    try:
        r = requests.get(url, params=params, timeout=settings.ENDAGA['BTS_REQUEST_TIMEOUT_SECS'])
        if r.status_code >= 200 and r.status_code < 300:
            print "async_get SUCCESS. url: '%s' (%d). Response was: %s" % (r.url, r.status_code, r.text)
            return r.status_code # request went through, great
        else:
            # something bad happened that shouldn't have happened, log it
            print "async_get FAIL. url: '%s' (%d). Response was: %s" % (r.url, r.status_code, r.text)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise self.retry(countdown=retry_delay, max_retries=max_retries)
    except Exception as e:
        print "async_get ERROR. url: '%s' exception: %s" % (url, e)
        raise


@app.task(bind=True)
def update_credit(self, imsi, update_id):
    """Send a request to a BTS to update credits for an IMSI.

    First we query for an existing PendingCreditUpdate.  If it exists, we try
    to send this info to the BTS.  If we successfully send, we delete the
    PendingCreditUpdate.  Then subsequent runs of this task (with a unique
    update_id) will not find a PendingCreditUpdate and the task will simply
    exit.

    If we fail to send this info to the BTS, the task will retry for some
    amount of time.
    """
    try:
        update = PendingCreditUpdate.objects.get(
            uuid=update_id, subscriber__imsi=imsi)
    except PendingCreditUpdate.DoesNotExist:
        # The PendingCreditUpdate no longer exists because it has been applied
        # already, so we simply exit.
        return

    # If we got the PendingCreditUpdate, send the request.
    bts = update.subscriber.bts
    url = bts.inbound_url + "/config/add_credit"
    jwt = bts.generate_jwt(update.req_params())
    try:
        request = requests.get(
            url, params={'jwt': jwt},
            timeout=settings.ENDAGA['BTS_REQUEST_TIMEOUT_SECS'])
        if request.status_code >= 200 and request.status_code < 300:
            print "update_credit SUCCESS. id=%s, imsi=%s, amount=%s. (%d)" % (
                update_id, imsi, update.amount, request.status_code)
            update.delete()
            bts.mark_active()
            bts.save()
        else:
            message = ("update_credit FAIL. id=%s, imsi=%s, (bts=%s), "
                       "amount=%s. (%d)")
            print message % (update_id, imsi, bts.uuid, update.amount,
                             request.status_code)

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        # We could not connect or timed out.
        print "update_credit ERROR. id=%s, imsi=%s, amount=%s. (RETRY)" % (
            update_id, imsi, update.amount)
        # Retry the task for some amount of time.
        # TODO(matt): refactor magic constants here.
        raise self.retry(countdown=10, max_retries=6*60*24)
    except Exception as caught_exception:
        print "update_credit ERROR. update_id=%s, imsi=%s, amount=%s. (%s)" % (
            update_id, imsi, update.amount, caught_exception)
        raise


@app.task(bind=True)
def vacuum_inactive_subscribers(self):
    """Deletes subscribers with no outbound activity.

    Each network can turn on this feature to automatically deactivate
    subscribers.  This runs this as a periodic task managed by celerybeat.
    """
    for network in Network.objects.iterator():
        # Do nothing if subscriber vacuuming is disabled for the network.
        if not network.sub_vacuum_enabled:
            continue
        inactives = network.get_outbound_inactive_subscribers(
            network.sub_vacuum_inactive_days)
        for subscriber in inactives:
            if subscriber.prevent_automatic_deactivation:
                continue
            print 'vacuuming %s from network %s' % (subscriber.imsi, network)
            subscriber.deactivate()
            # Sleep a bit in between each deactivation so we don't flood the
            # BTS.
            time.sleep(2)

@app.task(bind=True)
def facebook_ods_checkin(self):
    """Pushes model information to ODS
    Runs each miniute
    """
    app_id = settings.FACEBOOK['APP_ID']
    app_secret = settings.FACEBOOK['APP_SECRET']
    ods_url = 'https://graph.facebook.com/ods_metrics?access_token=%s|%s' % \
        (app_id, app_secret)
    one_minute_ago = django.utils.timezone.now() - datetime.timedelta(minutes=1)

    datapoints = []
    datapoints.append({
        'entity': 'etagecom.cloud.worker',
        'key': 'is_active',
        'value': 1
    })
    for bts in BTS.objects.iterator():
        if bts.last_active:
            network = bts.network
            ent_name = 'etagecom.%s.%s.%s.%s' % (network.environment,
                network.id, network.name, bts.uuid)
            datapoint = {'entity': ent_name,
                         'key': 'is_active',
                         'value': int(bts.status == 'active')}
            datapoints.append(datapoint)

            if bts.last_active >= one_minute_ago:
                # usage events for this bts since it was last active, group and sum by kind
                for event_group in UsageEvent.objects.filter(bts=bts).filter(
                    date_synced__gte=bts.last_active).values('kind').annotate(
                        count_kind=Count('id')).order_by():
                    datapoints.append({'entity': ent_name,
                                       'key': event_group['kind'],
                                       'value': event_group['count_kind']})

                # stats for this bts since it was last active, group and average by key
                for timeseries_stat in TimeseriesStat.objects.filter(bts=bts).filter(
                    date__gte=bts.last_active).values('key').annotate(
                        average_value=Avg('value')).order_by():
                    datapoints.append({'entity': ent_name,
                                       'key': timeseries_stat['key'],
                                       'value': timeseries_stat['average_value']})

                # subscribers that have camped within the T3212 window on this BTS are considered active
                t3212_mins = int(ConfigurationKey.objects.get(
                    network=bts.network, key="GSM.Timer.T3212").value)
                t3212_window_start = bts.last_active - datetime.timedelta(minutes=t3212_mins)
                camped_subscribers = Subscriber.objects.filter(bts=bts).filter(
                    last_camped__gte=t3212_window_start)
                datapoints.append({'entity': ent_name,
                                   'key': 'camped_subscribers',
                                   'value': camped_subscribers.count()})


    requests.post(ods_url, data={'datapoints': json.dumps(datapoints)})

@app.task(bind=True)
def downtime_notify(self):
    """Sends out notifcation to a user if a BTS has gone down.
    Runs every `BTS_INACTIVE_TIMEOUT_SECS`
    """
    timeout_secs = settings.ENDAGA['BTS_INACTIVE_TIMEOUT_SECS']

    # get nexmo config
    try:
        nexmo_number_out = settings.ENDAGA['NEXMO_NOTIFICATION_NUMBER']
        nexmo_provider = NexmoProvider(settings.ENDAGA['NEXMO_ACCT_SID'],
                           settings.ENDAGA['NEXMO_AUTH_TOKEN'],
                           settings.ENDAGA['NEXMO_INBOUND_SMS_URL'],
                           None, #outbound_sms_url
                           settings.ENDAGA['NEXMO_INBOUND_VOICE_HOST'])
    except KeyError:
        nexmo_number_out = None
        nexmo_provider = None

    # get mailgun config
    try:
        support_email = settings.TEMPLATE_CONSTANTS['SUPPORT_EMAIL']
    except KeyError:
        support_email = None

    for bts in BTS.objects.filter(status='active'):

        # Safety check - should not be hit
        if not bts.last_active:
            continue

        checkin_secs = (django.utils.timezone.now() -
            bts.last_active).total_seconds()

        # Only send out notifications after one period of no activity, if BTS has 'active' status
        if timeout_secs < checkin_secs:
            data = {
                'bts_uuid_short': bts.uuid[:6],
                'bts_uuid': bts.uuid,
                'bts_nickname': bts.nickname,
            }

            if bts.nickname:
                email_subj = ("Alert open: BTS %s (%s...) offline"
                                % (bts.nickname, bts.uuid[:6]))
            else:
                email_subj = "Alert open: BTS %s offline" % (bts.uuid)
            email_msg = render_to_string("internal/bts_down_email.html", data)
            sms_msg = render_to_string("internal/bts_down_sms.html", data)

            for email in bts.network.notify_emails.split(','):
                email = email.strip()
                if support_email and email:
                    try:
                        send_mail(email_subj, email_msg, support_email, [email])
                    except Exception as e:
                        # log the error, but ignore it.
                        print ("email fail sub: '%s' msg: '%s' frm: '%s' "
                               "to: '%s' exception: %s" % (email_subj,
                                   email_msg, support_email, email, e))

            # We blindly assume the SMS is <140 char
            for number in bts.network.notify_numbers.split(','):
                number = number.strip()
                if nexmo_number_out and nexmo_provider and number:
                    try:
                        nexmo_provider.send(number, nexmo_number_out, sms_msg)
                    except Exception as e:
                        print "sms fail: to: %s from: %s msg: %s" % (number, nexmo_number_out, sms_msg)

            # Mark BTS as inactive
            bts.status = 'inactive'
            bts.save()
            down_event = SystemEvent(
                    date=django.utils.timezone.now(), bts=bts,
                    type='bts down')
            down_event.save()

@app.task(bind=True)
def async_email(self, subject, body, from_, to_list):
    send_mail(subject, body, from_, to_list)

@app.task(bind=True)
def sms_notification(self, body, to):
    try:
        nexmo_number_out = settings.ENDAGA['NEXMO_NOTIFICATION_NUMBER']
    except KeyError:
        return # Do nothing if not configured

    nexmo_provider = NexmoProvider(settings.ENDAGA['NEXMO_ACCT_SID'],
                       settings.ENDAGA['NEXMO_AUTH_TOKEN'],
                       settings.ENDAGA['NEXMO_INBOUND_SMS_URL'],
                       None, #outbound_sms_url
                       settings.ENDAGA['NEXMO_INBOUND_VOICE_HOST'])

    nexmo_provider.send(to, nexmo_number_out, body)

@app.task(bind=True)
def req_bts_log(self, obj, retry_delay=60*10, max_retries=432):
    """Sends a request to a BTS config endpoint to collect a particular
    log file.
    """
    # default retry is every 10 min for 3 days
    print "attempting to req_bts_log request to '%s'" % (obj.bts)
    try:
        obj.status = 'trying'
        url = obj.bts.inbound_url + "/config/req_log"
        params = {'jwt': obj.bts.generate_jwt(obj.req_params())}
        r = requests.get(url, params=params, timeout=settings.ENDAGA['BTS_REQUEST_TIMEOUT_SECS'])
        if r.status_code >= 200 and r.status_code < 300:
            print "req_bts_log SUCCESS. url: '%s' (%d). Response was: %s" % (r.url, r.status_code, r.text)
            obj.status = 'accepted'
        else:
            # something bad happened that shouldn't have happened, log it
            print "req_bts_log FAIL. url: '%s' (%d). Response was: %s" % (r.url, r.status_code, r.text)
            obj.status = 'error'
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        obj.status = 'error'
        raise self.retry(countdown=retry_delay, max_retries=max_retries)
    except Exception as e:
        obj.status = 'error'
        print "req_bts_log ERROR. url: '%s' exception: %s" % (url, e)
        raise
    finally:
      obj.save()
