"""A simple debug "echoing" view.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from django.http import HttpResponse


def debug_view(request):
    """A view that echoes back what it receives."""
    if request.method == 'POST':
        for k in request.POST:
            print "%s: %s" % (k, request.POST[k])

    elif request.method == 'GET':
        for k in request.GET:
            print "%s: %s" % (k, request.GET[k])

    return HttpResponse()
