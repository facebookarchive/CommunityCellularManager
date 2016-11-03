"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

class MockEnvoy(object):
    """Mocking the envoy package."""

    def __init__(self, return_text):
        self.return_text = return_text

    class Response(object):
        """Mock envoy response."""

        def __init__(self, return_text):
            self.std_out = return_text
            self.status_code = 0

    def run(self, *args, **kwargs):
        return self.Response(self.return_text)
