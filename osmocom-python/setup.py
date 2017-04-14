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

VERSION = '0.0.5'


setup(
  name='osmocom',
  version=VERSION,
  description='Osmocom VTY client',
  long_description=README,
  author='Facebook',
  author_email='CommunityCellularManager@fb.com',
  packages=['osmocom'],
  install_requires=[
  ],
)
