"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""
from django.conf.urls import url

import sason.views

urlpatterns = [
    url(r'^ping/',
        sason.views.Ping.as_view()),
    url(r'^request/',
        sason.views.Request.as_view()),
    url(r'^acquire/',
        sason.views.Acquire.as_view()),
]
