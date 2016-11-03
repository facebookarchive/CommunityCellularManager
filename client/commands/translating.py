"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Fabric commands related to translation."""
from fabric.api import cd
from fabric.api import run
from fabric.contrib.files import exists


def extract_pot():
    """Extract the translatable strings from the whole project, put them into
    endaga-lang.
    """
    with cd('~/client'):
        # note the output of this should be version controlled.
        run('pybabel extract .  -k gt -c NOTE --no-wrap --no-default-keywords'
            ' --project="Endaga"'
            ' --copyright-holder="Facebook, Inc."'
            ' --msgid-bugs-address=shasan@fb.com'
            ' -o endaga-lang/endaga.pot')


def compile_lang():
    """Update the .mo and .po files in the locales."""
    with cd('~/client/endaga-lang'):
        locales = ['en', 'es', 'id', 'fil']
        for locale in locales:
            if exists("locale/" + locale):
                run('pybabel update --ignore-obsolete --no-wrap -l %s'
                    ' -i endaga.pot -d ./locale -D endaga' % (locale,))
            else:
                run('pybabel init --no-wrap -l %s -i endaga.pot -d ./locale'
                    ' -D endaga' % (locale,))
        run('pybabel compile -d locale -f -D endaga')
