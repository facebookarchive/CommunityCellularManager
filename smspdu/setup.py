#! /usr/bin/env python
"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from distutils.core import setup

from smspdu import __version__, __doc__

# perform the setup action
setup(
    name="smspdu",
    version=__version__,
    description="SMS PDU encoding and decoding, including GSM-0338 characters",
    long_description=__doc__,
    author="Richard Jones",
    author_email="rjones@ekit-inc.com",
    packages=['smspdu'],
    url='http://pypi.python.org/pypi/smspdu',
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: BSD License',
    ],
)

# vim: set filetype=python ts=4 sw=4 et si
