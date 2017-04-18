"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Setup for core.

Installing this package installs core software, including FS scripts used in
our dialplan/chatplans.
"""

from setuptools import setup

from core import VERSION

# Load the readme.
with open('README.md') as f:
    README = f.read()


GH_BASEURL = 'http://github.com/facebookincubator/CommunityCellularManager'

setup(
    name='endaga-core',
    version=VERSION,
    description='Endaga client core',
    long_description=README,
    url=GH_BASEURL,
    author='Facebook',
    author_email='CommunityCellularManager@fb.com',
    packages=[
        'core',
        'core.federer_handlers',
        'core.fake_phone',
        'core.apps',
        'core.gprs',
        'core.subscriber',
        'core.sms',
        'core.sms.freeswitch',
        'core.bts',
        'core.db',
    ],
    #hack removal of flup
    #it is a dependency but we include it in the
    #fpm call as the pip version breaks python2 compatibility
    install_requires=[
        "argparse>=1.4.0",
        "ccm-common>=0.6.0",
        "docopt==0.6.2",
        "delegator.py>=0.0.8",
        "humanize==0.5.1",
        "itsdangerous==0.22",
        "netifaces==0.10.5",
        "Paste==1.7.5.1",
        "phonenumbers==6.2.0",
        "psutil==3.1.1",
        "psycopg2==2.6",
        "PyYAML==3.10",
        "requests==2.6.2",
        "sms-utilities==0.0.4",
        "snowflake==0.0.3",
        "web.py>=0.40",
        "python-dateutil==2.4.2",
        "pytz==2015.7",
        "snowflake>=0.0.3",
        "supervisor>=0.4.0",
        "pexpect>=4.2.1",
        "ptyprocess>=0.5.1",
    ],
    scripts=[
        'scripts/ccm_hlr',
        'scripts/reset-registration',
        'scripts/set_configdb_defaults',
        'scripts/credit_cli',
        'scripts/endaga_db_get',
        'scripts/endaga_db_set',
        'scripts/endagad',
        'scripts/federer_server',
        'scripts/update_installed_versions',
        'scripts/endaga-gprsd',
        'scripts/fake_phone_client',
        'scripts/rsyslog_processor',
        'scripts/log_level',
    ],
    data_files=[
        ('/usr/share/freeswitch/scripts', [
            'scripts/freeswitch/endaga_currency.py',
            'scripts/freeswitch/endaga_i18n.py',
            'scripts/freeswitch/endaga_camped.py',
            'scripts/freeswitch/endaga_config_get.py',
            'scripts/freeswitch/VBTS_Get_IP.py',
            'scripts/freeswitch/VBTS_Get_Port.py',
            'scripts/freeswitch/VBTS_Get_CallerID.py',
            'scripts/freeswitch/VBTS_Get_Account_Balance.py',
            'scripts/freeswitch/VBTS_Get_Sec_Avail.py',
            'scripts/freeswitch/VBTS_Get_IMSI_From_Number.py',
            'scripts/freeswitch/VBTS_Get_Service_Tariff.py',
            'scripts/freeswitch/VBTS_Parse_SMS.py',
            'scripts/freeswitch/VBTS_Send_SMS.py',
            'scripts/freeswitch/VBTS_Send_SMS_Direct.py',
            'scripts/freeswitch/VBTS_Canonicalize_Phone_Number.py',
            'scripts/freeswitch/VBTS_Transfer_Credit.py',
            'scripts/freeswitch/VBTS_Get_Auth_From_IMSI.py',
            'scripts/freeswitch/VBTS_Get_Username_From_IMSI.py',
            'scripts/freeswitch/VBTS_Get_IMSI_From_Username.py',
        ]),
        ('/etc/openvpn/', [
            'conf/registration/etage-bundle.crt',
        ]),
        ('/etc/supervisor/conf.d/', [
            'conf/registration/openvpn.conf',
            'conf/registration/runwritable.conf',
            'conf/registration/endagad.conf',
            'conf/endaga-gprsd/endaga-gprsd-supervisor.conf',
        ]),
        ('/etc/lighttpd/conf-enabled/', [
            'conf/10-federer-fastcgi.conf',
        ]),
        ('/etc/', [
            'conf/endaga-iptables.rules',
        ]),
        ('/etc/logrotate.d/', [
            'conf/logrotate/endaga',
        ]),
        ('/etc/rsyslog.d/', [
            'conf/rsyslog/00_endaga.conf',
            'conf/rsyslog/90_endaga.conf',
            'conf/rsyslog/endaga-python.rb',
            'conf/rsyslog/freeswitch.rb',
            'conf/rsyslog/lighttpd.rb',
        ]),
        ('/etc/network/if-pre-up.d/', [
            'conf/endaga-iptables-load',
        ]),
        ('/etc/sysctl.d/', [
            'conf/99-endaga-sysctl.conf',
        ]),
    ],
)
