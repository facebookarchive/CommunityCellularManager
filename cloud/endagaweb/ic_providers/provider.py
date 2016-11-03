"""
Base class for InterconnectProviders

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""
class InterconnectProvider(object):
    def get_existing_numbers(self):
        raise NotImplementedError

    def search_numbers(self):
        raise NotImplementedError

    def buy_number(self, number):
        raise NotImplementedError

    def setup_number(self, number, inbound_sms_url=None, inbound_voice_host=None):
        raise NotImplementedError

    def get_number(self, network):
        raise NotImplementedError

    def send(self, to, from_, body, to_country=None, from_country=None):
        raise NotImplementedError

