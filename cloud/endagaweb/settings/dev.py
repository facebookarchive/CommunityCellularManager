"""Django dev settings.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

# Flake8 doesn't handle star imports very well, so disable linting
# flake8: noqa

from __future__ import absolute_import

import os

from .admin import ADMIN_APPS
from .base import *
from fnmatch import fnmatch

class glob_list(list):
    def __contains__(self, key):
        for elt in self:
            if fnmatch(key, elt):
                return True
        return False


# Add the admin apps and debug toolbar in the dev env.
INSTALLED_APPS += ADMIN_APPS + [
    "debug_toolbar",
]

# We need the VM IP here so the debug toolbar will show up
INTERNAL_IPS = glob_list(["127.0.0.1", "10.0.*.*"])

# Point to the local certifier VM to allow BTS registration
ENDAGA['KEYMASTER'] = os.environ.get("KEYMASTER", "192.168.40.40")

# Location of the sason (or other) SAS
SASON_REQUEST_URL = os.environ.get("SASON_REQUEST_URL",
                                   "http://192.168.40.10:8000/sason/request/")
SASON_ACQUIRE_URL = os.environ.get("SASON_ACQUIRE_URL",
                                   "http://192.168.40.10:8000/sason/acquire/")

# in dev environment we serve static files directly, not via nginx, so
# put them somewhere more convenient than /var/www
STATIC_ROOT = os.path.join(os.environ["HOME"], "static")
