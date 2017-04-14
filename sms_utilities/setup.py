"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Package definition."""

from setuptools import setup


with open('requirements.txt') as f:
    required_libs = f.readlines()

with open('readme.md') as f:
    readme = f.read()

github_url = 'https://github.com/facebookincubator/CommunityCellularManager/sms_utilities'
version = '0.0.4'
download_url = '%s/%s' % (github_url, version)

setup(
    name='sms_utilities',
    version=version,
    description='SMS encoding and decoding utilities',
    long_description=readme,
    url=github_url,
    download_url=download_url,
    author='Facebook',
    author_email='CommunityCellularManager@fb.com',
    license='BSD',
    packages=['sms_utilities'],
    install_requires=required_libs,
    zip_safe=False
)
