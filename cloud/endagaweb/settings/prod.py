"""Base Django settings for endagaweb application.

These settings are appropriate for the production front-end web server,
which does not provide admin capabilities. It should be extended (by
staff.py) for the admin-capable front-end.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import

import logging
import os
from syslog import LOG_LOCAL0

import dj_database_url

# inherit base Django settings (more general than the endagaweb app)
from settings import *  # noqa: F403

# combine ccm.common.logger settings with Django logging
from ccm.common import logger

# Specify with DATABASE_URL variable.
DATABASES = {
    'default': dj_database_url.config(default=os.environ.get('DATABASE_URL')),
}
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

# Hosts/domain names that are valid for this site; required if DEBUG is False.
# ALLOWED_HOSTS env variable must be a comma-separated list of domains
ALLOWED_HOSTS = [_.strip() for _ in
                 os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')]

# List of finder classes that know how to find static files in various
# locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = os.environ["SECRET_KEY"]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'endagaweb/templates',
        ],
        'OPTIONS': {
            'context_processors': [
                # The default context processors.
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
            # We'll be conservative and assume a prod environment unless
            # told otherwise
            'debug': DEBUG,  # noqa: F405 (star import)
        },
    },
]

TEMPLATE_CONSTANTS = {
    'SITENAME': os.environ.get('ENDAGA_SITENAME', "Endaga"),
    'SUPPORT_EMAIL': os.environ.get('SUPPORT_EMAIL', "support@example.com"),
}

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'endagaweb.middleware.TimezoneMiddleware',
    'endagaweb.middleware.MultiNetworkMiddleware',
)

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of allauth.
    "django.contrib.auth.backends.ModelBackend",
    # Allauth specific authentication methods, such as login by e-mail.
    "allauth.account.auth_backends.AuthenticationBackend",
    "guardian.backends.ObjectPermissionBackend",
)

# Where to redirect for required logins.
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard'
SOCIALACCOUNT_ADAPTER = 'endagaweb.views.user.WhitelistedSocialAccountAdapter'
STAFF_EMAIL_DOMAIN_WHITELIST = ['fb.com']
SOCIALACCOUNT_QUERY_EMAIL = True
ENABLE_SOCIAL_LOGIN = os.environ.get('ENABLE_SOCIAL_LOGIN', False)

INSTALLED_APPS = [
    # 'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.facebook',
    'crispy_forms',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django_tables2',
    'endagaweb',
    'guardian',
    'rest_framework',
    'rest_framework.authtoken',
]

SITE_ID = 1

# We inherit the default Django logging configuration. Unfortunately
# there is a mixed use of standard logging module and custom
# ccm.common.logger within the endagaweb app. We can use the logger module's
# syslog handler, but we need to set the level appropriately.
#
# See http://docs.djangoproject.com/en/dev/topics/logging for more
# details on how to customize your logging configuration.

# allow syslog to be disabled, e.g., for testing (default = enabled)
_USE_SYSLOG = os.environ.get('DJANGO_DISABLE_SYSLOG', 'False').lower() != 'true'

_ENDAGAWEB_LOGGER = {
    'handlers': ['syslog'] if _USE_SYSLOG else [],
    'level': logging.DEBUG,  # overridden by handler's level
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,  # NOT the default
    'formatters': {
        'ccm.common.logger.verbose': {
            # we use this for syslog, which inserts its own timestamps
            'format': 'endagaweb ' + logger.VERBOSE_FORMAT,
        }
    },

    # Create a logger that sends all endagaweb log messages to syslog
    #
    # Note: currently the endagaweb app is inconsistent in how it logs
    # messages, which requires that we actually install the logger as root
    # of the logging hierarchy rather than endagaweb. That means other stuff
    # also gets sent to syslog.
    # TODO: t15748193 Make endagaweb log usage consistent
    'loggers': {
        '': _ENDAGAWEB_LOGGER,
    },
}

# configure the syslog handler if enabled
if _USE_SYSLOG:
    LOGGING.setdefault('handlers', {})['syslog'] = {
        'class': 'logging.handlers.SysLogHandler',
        'address': '/dev/log',
        'facility': LOG_LOCAL0,
        'formatter': 'ccm.common.logger.verbose',
        'level': os.environ.get('LOGGING_SYSLOG_LEVEL', 'WARN'),
    }

# Configure additional logging in dev/debug mode
if DEBUG:  # noqa: F405
    # send all endagaweb messages to the console (which then applies its
    # own priority-based filter, INFO by default per above). Note that we
    # use the CCM_LOGGER_NAME env var to direct ccm.common.logger messages
    # to endagaweb.logger, so they get handled just like other endagaweb
    # messages.
    #
    # See note above regarding endagaweb messages.
    LOGGING['formatters']['standard'] = {
        'format':
            "[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)s] %(message)s",
        'datefmt': "%d/%b/%Y %H:%M:%S"
    }
    LOGGING.setdefault('handlers', {})['console'] = {
        'level': os.environ.get('LOGGING_CONSOLE_LEVEL', 'INFO'),
        'class': 'logging.StreamHandler',
        'formatter': 'standard'
    }
    _ENDAGAWEB_LOGGER['handlers'] += ['console']

    # this sets the ccm.common.logger threshold to INFO
    logger.DefaultLogger.update_handler(level=logging.INFO)


# Use the bcrypt hasher first, followed by the defaults.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.SHA1PasswordHasher',
    'django.contrib.auth.hashers.MD5PasswordHasher',
    'django.contrib.auth.hashers.CryptPasswordHasher',
]

REST_FRAMEWORK = {
    # Use hyperlinked styles by default.
    # Only used if the `serializer_class` attribute is not set on a view.
    'DEFAULT_MODEL_SERIALIZER_CLASS':
        'rest_framework.serializers.HyperlinkedModelSerializer',
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        # 'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
        'rest_framework.permissions.AllowAny'
    ],
    # Adds TokenAuth to the list of default authenticators to allow users who
    # haven't logged in to take actions with just their token (via cURL for
    # instance).
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
}

CRISPY_TEMPLATE_PACK = 'bootstrap3'

SFTP = {
    'SFTP_HOST': os.environ.get('SFTP_HOST', "sftp_hostname"),
    'SFTP_USERNAME': os.environ.get('SFTP_USERNAME', "sftp_username"),
    'SFTP_PASSWORD': os.environ.get('SFTP_PASSWORD', "sftp_password")
}

FACEBOOK = {
    'APP_ID': os.environ['FACEBOOK_APP_ID'],
    'APP_SECRET': os.environ['FACEBOOK_APP_SECRET']
}

ENDAGA = {
    # Nexmo account info.
    'NEXMO_NOTIFICATION_NUMBER': os.environ.get('NEXMO_NOTIFICATION_NUMBER', None),
    'NEXMO_ACCT_SID': os.environ['NEXMO_ACCT_SID'],
    'NEXMO_AUTH_TOKEN': os.environ['NEXMO_AUTH_TOKEN'],
    'NEXMO_INBOUND_SMS_URL': os.environ.get(
        "INBOUND_SMS_URL", "http://api.endaga.com/api/v1/inbound/"),
    'NEXMO_INBOUND_VOICE_HOST': os.environ.get("INBOUND_VOICE_HOST",
                                               "sip.example.com"),

    # Kannel info
    'KANNEL_USERNAME': os.environ['KANNEL_USERNAME'],
    'KANNEL_PASSWD': os.environ['KANNEL_PASSWD'],
    'KANNEL_OUTBOUND_SMS_URL': os.environ.get('KANNEL_OUTBOUND_SMS_URL', "http://localhost:13005/cgi-bin/sendsms"),

    # Activity settings.
    'BTS_INACTIVE_TIMEOUT_SECS': 60 * 8,  # 8 minutes
    'BTS_REQUEST_TIMEOUT_SECS': 5,

    # Internal API.
    'INTERNAL_API': os.environ.get("INTERNAL_API", "localhost:8080"),
    'KEYMASTER': os.environ['KEYMASTER'],
    'VPN_SERVER_IP': os.environ.get("VPN_SERVER_IP", "192.168.40.60"),

    # Enable/disable billing for networks. If false, we ignore what's in the
    # network's account balance.
    'NW_BILLING': os.environ.get("NW_BILLING", "True").lower() == "true",

    # Maximum permissible validity(in days) limit for denomination
    'MAX_VALIDITY_DAYS': 10000,
}

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY",
                                "sk_test_YOURKEYHERE")

# Celery settings.
BROKER_URL = os.environ["BROKER_URL"]
CELERY_DEFAULT_QUEUE = os.environ["CELERY_DEFAULT_QUEUE"]
CELERY_QUEUES = {
    CELERY_DEFAULT_QUEUE: {
        'exchange': CELERY_DEFAULT_QUEUE,
        'exchange_type': 'topic',
        'binding_key': 'tasks.#',
    }
}

EMAIL_BACKEND = 'django_mailgun.MailgunBackend'
MAILGUN_ACCESS_KEY = os.environ.get("MAILGUN_ACCESS_KEY", 'key-testkeypleaseignore')
MAILGUN_SERVER_NAME = os.environ.get("MAILGUN_SERVER_NAME", '')

# File uploads
DEFAULT_FILE_STORAGE = 'endagaweb.util.storage.DatabaseStorage'

# To allow permissions for unauthenticated users, we introduce an anonymous User instance
ANONYMOUS_USER_NAME = 'AnonymousUser'

# Location of the sason (or other) SAS
SASON_REQUEST_URL = os.environ.get("SASON_REQUEST_URL", None)
SASON_ACQUIRE_URL = os.environ.get("SASON_ACQUIRE_URL", None)
SASON_RETRY_COUNT = 5

# Make recommended secure site settings be defaults
# These should only be overridden in dev environments

# Ensure we're using secure cookies, i.e., can only be sent over https
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Security middleware settings
SECURE_CONTENT_TYPE_NOSNIFF = True
