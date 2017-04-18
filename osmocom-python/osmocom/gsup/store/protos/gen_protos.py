"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import os
import sys
from grpc.tools import protoc
import grpc_tools


def gen_single_dir_binding(proto_files, include_paths, output_dir):
    '''Generates python and Go bindings for the .proto files
       @proto_files - list of .proto files to generate code for
       @include_paths - a list of include paths to resolve relative imports in .protos
       @output_dir - output directory to put generated code in
    '''

    cmds = ('--python_out=' + output_dir,
                '--grpc_python_out=' + output_dir)
    proto_files.sort()
    protoc.main(
        ('',) +
        tuple('-I' + path for path in include_paths) +
        cmds +
        tuple(filename for filename in proto_files))

def gen_bindings(input_dir, include_paths, output_dir):
    '''Generates python bindings for all .proto files in input dir
       @input_dir - input directory with .proto files to generate code for
       @include_paths - a list of include paths to resolve relative imports in .protos
       @output_dir - output directory to put generated code in
    '''
    print("Input, output and include dirs %s, %s and %s"
              % (input_dir, output_dir, include_paths))
    if not os.path.isdir(input_dir) or not os.path.isdir(output_dir):
        print("Error: check if input, output dirs %s, %s exist!"
              % (input_dir, output_dir))
        exit(1)

    if not all([os.path.isdir(include_path) for include_path in include_paths]):
       print("Error: check if include paths %s exist!" % include_paths)
       exit(1)

    # For each .proto file in the input_dir, generate the python stubs
    protos = []
    for root, _, names in os.walk(input_dir):
        for name in names:
            filename = os.path.join(root, name)
            extn = os.path.splitext(name)[1]
            if os.path.isfile(filename) and extn == ".proto":
                protos.append(filename)
    if len(protos) > 0:
        gen_single_dir_binding(protos, include_paths, output_dir)

def main():
    """
    Default main module. Generates .py code for all proto files
    specified by the arguments
    """
    if len(sys.argv) != 4:
        print("Usage: ./gen_protos.py <dir containing .proto's> <include paths CSV> <output dir>")
        exit(1)
    input_dir = sys.argv[1]
    include_paths = sys.argv[2].split(',')
    include_paths.append(grpc_tools.__path__[0] + '/_proto')
    output_dir = sys.argv[3]
    gen_bindings(input_dir, include_paths, output_dir)


if __name__ == "__main__":
    main()
