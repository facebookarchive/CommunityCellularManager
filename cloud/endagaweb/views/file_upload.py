"""A staff only view for serving files uploaded to DatabaseStorage.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import mimetypes

from django.http import (HttpResponse, HttpResponseBadRequest,
    HttpResponseForbidden, HttpResponseNotFound)

from endagaweb.models import FileUpload
from endagaweb.util.storage import DatabaseStorage


def file_view(request, fname):
    """A view that echoes back what it receives."""
    if not request.user.is_staff:
        return HttpResponseForbidden()

    if request.method != 'GET':
        return HttpResponseBadRequest()

    storage = DatabaseStorage()
    f = storage.open(fname, 'rb')
    if f is None:
        return HttpResponseNotFound()
    ftype, _ = mimetypes.guess_type(fname)
    response = HttpResponse(f.read(), content_type=ftype or 'application/octet-stream')
    response['Content-Disposition'] = 'inline; filename=%s' % fname
    response['Content-Length'] = '%d' % f.size
    return response
