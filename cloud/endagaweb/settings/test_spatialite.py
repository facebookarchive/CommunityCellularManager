"""
Use Django prod settings from endagaweb with as few changes as necessary
to make tests run under Buck/Sandcastle.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import os

from endagaweb.settings.staff import *  # noqa: F401, F403

# Use spatialite for unit tests
GEOS_LIBRARY_PATH = os.environ['GEOS_LIBRARY_PATH']
SPATIALITE_LIBRARY_PATH = os.environ['SPATIALITE_LIBRARY_PATH']

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.spatialite',
        'NAME': '/tmp/endaga.db',
    },
}

ROOT_URLCONF = 'endagaweb.urls'
