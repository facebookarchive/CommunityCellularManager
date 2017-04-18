"""VTY interface for OpenBSC
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from contextlib import contextmanager
import re
import select
import socket
import time

from .exceptions import VTYException, VTYChainedException

class BaseVTY(object):
    """VTY interface and context manager for OpenBSC."""
    EOL = '\r\n'
    BUF_SIZE = 4096 #libosmocore vty buf size
    TIMEOUT = 3.0
    SOCKET_ERRORS = (socket.error, socket.herror, socket.timeout)

    def __init__(self, app_name, host='127.0.0.1', port=4242, timeout=None):
        """Interface for Osmocom VTY application.

        `app_name` is the name that appears on the VTY shell
        and is used to determine when we have reached the end of
        a repsonse.
        """
        self.app_name = app_name
        self.host = host
        self.port = port

        self.is_enable_mode = False
        self.is_configure_mode = False
        self._socket_obj = None
        self._context_depth = 0
        self._buf = ''

        self.EOM = self.EOL + self.app_name

        if timeout is not None:
            self.TIMEOUT = timeout

    @contextmanager
    def _socket(self):
        try:
            yield self._socket_obj
        except self.SOCKET_ERRORS as e:
            self._socket_obj = None
            raise VTYChainedException(e)
        except VTYException as e:
            self._socket_obj = None
            raise e

    def open(self):
        """Opens the socket with Osmocom VTY"""
        if self._socket_obj:
            raise VTYException('Connection already established')
        try:
            self._socket_obj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket_obj.setblocking(1)
            self._socket_obj.connect((self.host, self.port))
        except self.SOCKET_ERRORS as e:
            self._socket_obj = None
            raise VTYChainedException(e)
        self.sendrecv('')


    def close(self):
        """Closes the socket with Osmocom VTY"""
        if not self._socket_obj:
            raise VTYException('Connection not open')
        self._socket_obj.close()
        self._socket_obj = None

    def sendrecv(self, command):
        """Sends a command to the VTY and return the response"""
        if not self._socket_obj:
            raise VTYException('Connection not open')

        with self._socket() as s:
            s.sendall(bytearray(command + '\r', 'utf-8'))
            has_data = lambda : len(select.select([s], [], [], self.TIMEOUT)[0])
            while self.EOM not in self._buf and has_data():
                recv = bytearray(s.recv(self.BUF_SIZE)).decode('utf-8', 'ignore')
                if not len(recv):
                    raise VTYException('Connection died during recv')
                self._buf += recv

            if self.EOM not in self._buf:
                raise VTYException("Connection stopped responding or timed out: %s", self._buf)

        # Find the the response by seeking past the command to the next line and reading until the first EOM.
        resp_start = self._buf.find(command) + len(command + self.EOL)
        resp_end = resp_start + self._buf[resp_start:].find(self.EOM)
        ret = self._buf[resp_start:resp_end].strip()
        self._buf = self._buf[resp_end:].lstrip()

        if 'Unknown command' in ret:
            raise ValueError('Invalid command: %s' % command)

        return ret

    def running_config(self):
        """Reads and parses the running configuration into
        a heirarchical object. If the next line has an indentation
        the next entries are added to a sub-object with the key being
        the current entry. If this entry is indexed, the next entries
        are stored under a sub-sub-object with the key being the index"""
        running_config = {}
        cur_object = running_config
        indent_stack = [0]
        key_stack = []

        with self.enable_mode():
            running_config_raw = self.sendrecv('show running-config')
            running_config_lines = running_config_raw.split('\n')

        for i in range(1, len(running_config_lines)-1):
            line = running_config_lines[i].strip()
            line_tokens = line.split()

            # skip comments
            if line[0][0] == '!':
                continue

            # if we see a negation, fix the key name
            if line_tokens[0] == "no":
                line_tokens.pop(0)
                line_tokens.append("no")
            entry_name = " ".join(line_tokens[:-1])
            entry_value = line_tokens[-1]

            # if line is only one word set the name instead of value
            if entry_name == "":
                entry_name = entry_value
                entry_value = ""

            # peek at the next line to determine if we will
            # create a new sub-object
            if i+1 < len(running_config_lines):
                next_line = running_config_lines[i+1]
                match = re.search('^\s*', next_line)
                next_indent = len(match.group(0))

            # this is the name of a new sub-object
            if next_indent > indent_stack[-1]:
                # this is an indexed sub-object
                # so we add the object name and the index to the stack
                if entry_value.isdigit():
                    section_name = [entry_name, entry_value]
                else:
                    section_name = [line]
                indent_stack.extend([next_indent] * len(section_name))
                key_stack.extend(section_name)
            # this is an entry in the current object
            else:
                cur_object[entry_name] = entry_value

            # navigate down the indent stack to next_indent
            while next_indent < indent_stack[-1]:
                indent_stack.pop()
                key_stack.pop()

            # navigate up the key stack to the next sub-object
            cur_object = running_config
            for key in key_stack:
                if key not in cur_object:
                    cur_object[key] = {}
                cur_object = cur_object[key]

        return running_config

    @contextmanager
    def enable_mode(self):
        """Context manager to raise mode to VTY_ENABLE."""
        self.sendrecv('enable')
        self.is_enable_mode = True
        try:
            yield
        finally:
            self.sendrecv('disable')
            self.is_enable_mode = False

    @contextmanager
    def configure_mode(self):
        """Context manager to raise mode to VTY_CONFIGURE."""
        with self.enable_mode():
            while not self.is_configure_mode:
                if 'locked' in self.sendrecv('configure terminal'):
                    print('waiting for lock')
                    time.sleep(self.TIMEOUT)
                else:
                    self.is_configure_mode = True
            try:
                yield
            finally:
                self.sendrecv('exit')
                self.is_configure_mode = False

    @contextmanager
    def configure(self, level):
        """Context manager to put VTY into configuring a particular module."""
        if not self.is_configure_mode:
            raise RuntimeError('you need to use a configure context')
        self.sendrecv(level)
        try:
            yield
        finally:
            self.sendrecv('exit')

    def __enter__(self):
        """For constructing VTY connection context"""
        if self._context_depth == 0:
            self.open()
        self._context_depth += 1
        return self

    def __exit__(self, type, value, traceback):
        """For exiting VTY connection context"""
        self._context_depth -= 1
        if self._context_depth == 0 and self._socket_obj:
            self.close()
        return False

    def _parse_show(self, resp):
        """Parse the response from the show command, iterating through
        each of the regex engines and collecting the groiups into a single dictionary.
        """
        data = {}
        for engine in self.PARSE_SHOW:
            match = engine.search(resp)
            if match:
                data.update(match.groupdict())
        return data
