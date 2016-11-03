"""Django prod settings.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from .base import *

# Ensure we're using secure cookie
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Security middleware settings
SECURE_CONTENT_TYPE_NOSNIFF = True
