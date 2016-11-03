"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""The openbts-python package."""

from setuptools import setup


with open('readme.md') as f:
  README = f.read()


VERSION = '0.1.15'


setup(
  name='openbts',
  version=VERSION,
  description='OpenBTS NodeManager client',
  long_description=README,
  url='http://github.com/endaga/openbts-python',
  download_url=('https://github.com/endaga/openbts-python/tarball/%s' %
                VERSION),
  author='Shaddi Hasan',
  author_email='shasan@fb.com',
  license='BSD',
  packages=['openbts'],
  install_requires=[
    "enum34==1.0.4",
    "envoy==0.0.3",
    "pyzmq==14.5.0",
  ],
  zip_safe=False
)
