"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""The osmocom-python package."""

from setuptools import setup


with open('README.md') as f:
  README = f.read()

VERSION = '0.1.0'


setup(
  name='osmocom',
  version=VERSION,
  description='Osmocom VTY client',
  long_description=README,
  author='Facebook',
  author_email='CommunityCellularManager@fb.com',
  packages=['osmocom.gsup',
            'osmocom.gsup.store',
            'osmocom.gsup.store.protos',
            'osmocom.gsup.crypto',
            'osmocom.gsup.protocols',
            'osmocom.vty'],
  scripts=['scripts/osmocom_hlr'],
  install_requires=['grpcio==1.0.4',
                    'aiohttp>=0.17.2'],
  extras_require={'dev': ['grpcio-tools>=1.0.0',
                          'nose==1.3.7']},
)
