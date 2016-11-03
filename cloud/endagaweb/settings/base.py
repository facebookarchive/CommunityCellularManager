"""Base django settings for endagaweb application.

We expect this to be imported and overriden by something like dev.py and
prod.py.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import os
import dj_database_url
from settings import *

# Specify with DATABASE_URL variable.
DATABASES = {
    'default': dj_database_url.config(default=os.environ.get('DATABASE_URL')),
}
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

# Hosts/domain names that are valid for this site; required if DEBUG is False.
# ALLOWED_HOSTS env variable must be a comma-seperated list of domains
ALLOWED_HOSTS = [_.strip() for _ in \
    os.environ.get('ALLOWED_HOSTS', "localhost").split(",")]

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
            'loaders' : [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
            # We'll be conservative and assume a prod environment unless told otherwise
            'debug' : DEBUG,
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

INSTALLED_APPS = [
    # 'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # 'allauth.socialaccount.providers.facebook',
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

# A sample logging configuration. The only tangible logging performed by this
# configuration is to send an email to the site admins on every HTTP 500 error
# when DEBUG=False.  See http://docs.djangoproject.com/en/dev/topics/logging
# for more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}

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
        #'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
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
