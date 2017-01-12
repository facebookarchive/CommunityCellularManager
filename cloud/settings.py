"""Base django settings for endagaweb project.

We expect this to be imported and overriden by the settings of individual
subprojects

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import os

#We'll be conservative and assume a prod environment unless told otherwise
DEBUG = bool(os.environ.get('DEBUG', False) == "True")

TIME_ZONE = 'UTC'

LANGUAGE_CODE = 'en-us'

SITE_ID = 1

USE_I18N = True

USE_L10N = True

USE_TZ = True

ROOT_URLCONF = 'urls'

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

MANAGERS = ADMINS

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.  Don't
# put anything in this directory yourself; store your static files in apps'
# "static/" subdirectories and in STATICFILES_DIRS.  Example:
# "/var/www/example.com/static/"
#
# In CCM we serve static files using nginx, so we have to ensure that the
# nginx configuration maps STATIC_URL (below) to this location.
STATIC_ROOT = '/var/www/static'

# URL prefix for static files.  And additional locations of static files.
STATIC_URL = '/static/'
STATICFILES_DIRS = ()

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'endagaweb.wsgi.application'
