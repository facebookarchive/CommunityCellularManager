"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Fabric commands for config packaging."""
from fabric.api import cd
from fabric.api import env
from fabric.api import run

from commands.translating import compile_lang, extract_pot


def package_freeswitch_config():
    """Packages our freeswitch config files and drops them in /etc."""
    run('mkdir -p ~/endaga-packages')
    path = '~/client/conf/freeswitch-conf-endaga'
    print('packaging %s' % path)
    with cd(path):
        run('fpm -s dir -t %s -a all -n freeswitch-conf-endaga -v `cat VERSION`'
            ' --description "Endaga Freeswitch config files"'
            ' freeswitch=/etc' % env.pkgfmt)
        run('mv *.%s ~/endaga-packages' % env.pkgfmt)


def package_endaga_lang_config():
    """Packages our translation files."""
    # First generate all necessary .mo files.
    extract_pot()
    compile_lang()
    run('mkdir -p ~/endaga-packages')
    path = '~/client/endaga-lang'
    print('packaging %s' % path)
    with cd(path):
        run('fpm -s dir -t %s -a all -n endaga-lang -v `cat VERSION`'
            ' --description "Endaga translation files"'
            ' locale=/usr/share' % env.pkgfmt)
        run('mv *.%s ~/endaga-packages' % env.pkgfmt)
