#!/usr/bin/env python2

"""
Package the CCM common components.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import imp
import sys

from fabric import api

# get the default env settings from the client fabfile
sys.path = ['../client'] + sys.path
(f, path, desc) = imp.find_module('fabfile')
if f is not None:
    client_fabfile = imp.load_module('client_fabfile', f, path, desc)
    f.close()

# this just disables warnings about default behaviour
api.env.fpm_flags = "--deb-no-default-config-files"

RUNCMD = api.run


@api.task
def dev():
    with api.lcd('../client'):
        client_fabfile.dev()


@api.task
def localhost():
    api.env.hosts = ['localhost']
    global RUNCMD
    RUNCMD = api.local


@api.task
def osmocom():
    client_fabfile.osmocom()


@api.task
def package_common_lib():
    RUNCMD("fpm"
           " -s python"      # read from standard Python setup.py
           " --python-pip pip3 --python-bin python3"
           " --python-package-name-prefix python3"
           " -t %(pkgfmt)s"  # set output package format
           " -f"             # overwrite any existing file
           " -p ~/endaga-packages"  # put output in endaga-packages
           " %(fpm_flags)s"  # pass in extra flags
           " ~/common/setup.py" %
           api.env)
