"""
Various utilities for configuring system-level services and settings.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from datetime import datetime
from datetime import timedelta
import glob
import gzip
import os
import re
import subprocess

import dateutil.parser
import dateutil.tz
import delegator
import netifaces
import psutil
import pytz

from ccm.common import logger
from core.config_database import ConfigDB

def log_stream(log_path, window_start=None, window_end=None):
    """Given a path to a log file, this method returns an ordered
    stream of entries. This stream supports log rotation and archival
    assuming rotated logs have the same path followed by a dot suffix.
    Archived logs can be gz compressed. This also supports limiting
    the log entries to a particular time window.

    All log entries must contain timestamps that contain no spaces and
    must be timezone aware.

    Arguments:
        log_path: the absolute path to the log
        window_start: a timezone aware datetime. If None is specified
            it is assumed from the beginning of time.
        window_end: a timezone aware datetime. If None is specified
            it is assumed until the current time.
    """
    def open_raw_or_gzip(fname, mode):
        if fname[-3:] == '.gz':
            return gzip.open(fname, mode)
        else:
            return open(fname, mode)

    if window_start is None:
        window_start = datetime.fromtimestamp(0, pytz.utc)
    if window_end is None:
        window_end = datetime.now(pytz.utc)

    fnames = glob.glob(log_path) + glob.glob("%s.*" % log_path)
    fnames.sort(key=os.path.getmtime)
    fnames = [f for f in fnames if datetime.fromtimestamp(
        os.path.getmtime(f), dateutil.tz.tzlocal()) >= window_start]

    for fname in fnames:
        with open_raw_or_gzip(fname, 'r') as f:
            for msg in f:
                try:
                    entry_time = dateutil.parser.parse(msg.split()[0])
                    if window_start <= entry_time <= window_end:
                        yield msg
                except (TypeError, ValueError):
                    # if timestamp isn't timezone aware, or unparseable skip it
                    pass

def uptime():
    """
    Returns (whole) seconds since boot, or -1 if failure.

    Note, requires existence of a /proc/uptime file, which should exist on most
    modern Linuxes.
    """
    with open("/proc/uptime") as f:
        try:
            return int(float(f.read().split()[0]))
        except:
            return -1


def get_vpn_ip():
    """
    Gets the system VPN IP, or returns None if no VPN is up.
    """
    try:
        # Pylint gets confused about the contents of this package for some
        # reason.
        # pylint: disable=no-member
        conf = ConfigDB()
        ifname = conf.get('external_interface')  # vpn_interface?
        assert ifname is not None, \
            "VPN interface ('external_interface') not configured"
        return netifaces.ifaddresses(ifname)[netifaces.AF_INET][0]['addr']
    except Exception:
        return None


def get_fs_profile_ip(profile_name):
    """Get the IP bound to a sofia profile in FS."""
    response = delegator.run('fs_cli -x "sofia status"')
    if response.return_code != 0:
        raise ValueError('error running "sofia status"')
    for line in response.out.split('\n'):
        if profile_name in line and 'profile' in line:
            data = line.split()[2]
            result = re.search('sip:mod_sofia@(.*):50', data)
            return result.group(1)


class SystemUtilizationTracker(object):
    """Tracks system utilization.

    We make this an object rather than a method because we send byte deltas and
    need to track the last number of bytes sent and received to compute those
    deltas.
    """

    def __init__(self):
        self.last_bytes_sent = 0
        self.last_bytes_received = 0

    def get_data(self):
        """Gets system utilization stats."""
        # Get system utilization stats.
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        network_io = psutil.net_io_counters()
        # Compute deltas for sent and received bytes.  Note this is system-wide
        # network usage and not necessarily GPRS-related.
        # TODO(matt): query on a specific interface..which one, I'm not sure.
        if self.last_bytes_sent == 0:
            bytes_sent_delta = 0
        else:
            bytes_sent_delta = network_io.bytes_sent - self.last_bytes_sent
        self.last_bytes_sent = network_io.bytes_sent
        if self.last_bytes_received == 0:
            bytes_received_delta = 0
        else:
            bytes_received_delta = (
                network_io.bytes_recv - self.last_bytes_received)
        self.last_bytes_received = network_io.bytes_recv
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'disk_percent': disk_percent,
            'bytes_sent_delta': bytes_sent_delta,
            'bytes_received_delta': bytes_received_delta,
        }

def upgrade_endaga(channel):
    """Upgrades the endaga metapackage."""
    # Validate.
    if channel not in ('stable', 'beta'):
        logger.error('cannot upgrade to the "%s" channel' % channel)
        return
    logger.notice('upgrading the endaga metapackage with channel %s' % channel)
    # Update packages.
    response = delegator.run('sudo apt-get update')
    if response.return_code != 0:
        message = 'Error while running "apt-get update": %s' % response.out
        logger.error(message)
    # Try a dry-run of the upgrade.
    command = ('sudo apt-get install --assume-yes --dry-run'
               ' --only-upgrade -t %s endaga' % channel)
    response = delegator.run(command)
    if response.return_code != 0:
        message = ('Error while dry running the endaga upgrade: %s' %
                   response.out)
        logger.error(message)
        return
    # Upgrade just the metapackage.
    command = ('sudo apt-get install --assume-yes'
               ' --only-upgrade -t %s endaga' % channel)
    response = delegator.run(command)
    if response.return_code != 0:
        message = 'Error while upgrading endaga: %s' % response.out
        logger.error(message)


def try_to_autoupgrade():
    """The gatekeeper of the upgrade_endaga method.

    Autoupgrades can be configured to run as soon as new software is available
    via the autoupgrade.in_window configdb key.  This method will invoke
    upgrade_endaga if autoupgrades are enabled.  If windowed upgrades are
    enabled, this will check if it's the right time and if an upgrade hasn't
    been run recently (default for "recently" is the last ten minutes).
    """
    conf = ConfigDB()
    window_duration = 10 * conf.get('registration_interval', 60)
    last_upgrade_format = '%Y-%m-%d %H:%M:%S'
    # Do nothing if autoupgrades are disabled.
    if not conf.get('autoupgrade.enabled', False):
        return
    # Also do nothing if there is no new metapackage available.  This info is
    # propagated for the beta and stable channels via the checkin response.
    channel = conf.get('autoupgrade.channel', 'stable')
    key = 'autoupgrade.latest_%s_version' % channel
    available_version = sortable_version(conf.get(key, '0.3.29'))
    installed_version = sortable_version(conf['endaga_version'])
    if available_version <= installed_version:
        return
    # If we're configured to only upgrade in a window (as opposed to as soon as
    # a new package is available), we need some additional checks.
    if conf.get('autoupgrade.in_window', False):
        # Do nothing if we've already performed an upgrade recently.
        last_upgrade = conf.get('autoupgrade.last_upgrade',
                                '2015-07-14 02:30:15')
        last_upgrade = datetime.strptime(last_upgrade, last_upgrade_format)
        now = datetime.utcnow()
        delta = (now - last_upgrade).total_seconds()
        if delta < window_duration:
            return
        # See if we're in the upgrade window.  Get the current time and the
        # window_start time as datetimes.  These are weird "date-less"
        # datetimes -- both dates will be 1-1-1900 but the part that we care
        # about, the times, will be comparable.
        window_format = '%H:%M:%S'
        now = datetime.strptime(now.strftime(window_format), window_format)
        window_start = conf.get('autoupgrade.window_start', '02:30:00')
        window_start = datetime.strptime(window_start, window_format)
        # Fail if we're currently before or after the window.
        if now < window_start:
            return
        if now > window_start + timedelta(seconds=window_duration):
            return
    # All checks pass, perform the upgrade and save the last upgraded time.
    upgrade_endaga(conf.get('autoupgrade.channel', 'stable'))
    conf['autoupgrade.last_upgrade'] = datetime.strftime(
        datetime.utcnow(), last_upgrade_format)


def sortable_version(version):
    """Converts '1.2.3' into '00001.00002.00003'"""
    # Version must be a string to split it.
    version = str(version)
    return '.'.join(bit.zfill(5) for bit in version.split('.'))


def verify_cert(_, cert_path, ca_path):
    """ Validate that cert has been signed by the specified CA. """
    try:
        # ugh, gotta explicitly send stderr to /dev/null with subprocess
        with open("/dev/null", "wb") as dev_null:
            subprocess.check_output("openssl verify -CAfile %s %s" %
                                    (ca_path, cert_path),
                                    shell=True, stderr=dev_null)
        return True
    except subprocess.CalledProcessError as ex:
        logger.warning("Unable to verify %s against %s: %s" %
                       (cert_path, ca_path, ex.output))
    return False
