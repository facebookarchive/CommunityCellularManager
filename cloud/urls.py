"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
from django.conf.urls import include, url

urlpatterns = [
    url(r'', include('endagaweb.urls')),
    url(r'^sason/', include('sason.urls'))
]
