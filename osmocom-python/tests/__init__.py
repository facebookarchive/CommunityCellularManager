"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""





import os


def get_fixture_path(name):
    ''' Get the path to the specified test fixture '''
    return os.path.join(os.path.dirname(__file__), 'fixtures', name)
