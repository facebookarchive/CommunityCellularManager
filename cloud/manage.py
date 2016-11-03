#!/usr/bin/env python
"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import os
import sys
import glob

if __name__ == "__main__":
    env_dir = 'envdir'
    env_vars = glob.glob(os.path.join(env_dir, '*'))
    for env_var in env_vars:
        with open(env_var, 'r') as env_var_file:
            os.environ.setdefault(env_var.split(os.sep)[-1],
                                  env_var_file.read().strip())

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
