"""Django staff site settings.

Staff site extends production site functionality with admin capabilities.
Keeping the two separate allows for operational changes to be applied to
them separately.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

# Flake8 doesn't handle star imports very well, so disable linting
# flake8: noqa

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .prod import *

# Add applications required for admin functionality
INSTALLED_APPS += [
    'django.contrib.admin',
    'django.contrib.admindocs',
    'logentry_admin',
    'loginas'
]

# Set django-allauth oauth token scope to get email addresses and set the
# post-login redirect to /dashboard.  We create a whitelist and only allow
# staff signup / login from these domains.  And we override an allauth Adapter
# to implement this whitelisting.
ACCOUNT_EMAIL_REQUIRED = True
LOGIN_REDIRECT_URL = '/dashboard'
STAFF_EMAIL_DOMAIN_WHITELIST = ['fb.com']
SOCIALACCOUNT_ADAPTER = 'endagaweb.views.user.WhitelistedSocialAccountAdapter'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
