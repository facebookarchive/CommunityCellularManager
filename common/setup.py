"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

#!/usr/bin/env python2

""" Setup for ccm/common - libraries shared between client and cloud. """

from setuptools import setup

from ccm.common import VERSION

# Load the readme.
with open('README.md') as f:
    README = f.read()

GH_BASE = "http://github.com/facebookincubator/CommunityCellularManager/"

setup(
    name='ccm-common',
    version=VERSION,
    description='CCM common libraries',
    long_description=README,
    url=GH_BASE,
    author='Facebook',
    author_email='CommunityCellularManager@fb.com',
    packages=[
        'ccm',
        'ccm.common',
        'ccm.common.crdt',
        'ccm.common.currency',
        'ccm.common.logger',
        'ccm.common.delta',
    ],
    install_requires=[
        'six',
    ],
)
