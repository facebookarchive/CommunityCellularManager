"""Sends and receives from a Kannel SMSC integration.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from django.conf import settings
from endagaweb.models import Number
from endagaweb.ic_providers import provider
import requests

class KannelProvider(provider.InterconnectProvider):
    """The Kannel client -- interfaces with Kannel directly."""
    def __init__(self, acct_sid, auth_token, inbound_sms_url, 
                 outbound_sms_url, inbound_voice_host, country='SE'):
        self.username = acct_sid
        self.password = auth_token
        self.outbound_sms_url = outbound_sms_url
        #shouldn't be used
        self.inbound_sms_url = inbound_sms_url
        #shouldn't be used
        self.inbound_voice_host = inbound_voice_host
        #shouldn't be used
        self.country = country

    def get_existing_numbers(self, ignore_country=True):
        """ Numbers are stored in our DB, there is no cloud to ask
        """
        raise NotImplementedError

    def get_number_info(self, number, count=10):
        """Get info on a number."""
        raise NotImplementedError

    def search_numbers(self, features="SMS,VOICE"):
        """ Numbers are stored in our DB, there is no cloud to search
        """
        raise NotImplementedError

    def buy_number(self, number):
        """Cannot buy numbers from direct relationships"""
        raise NotImplementedError

    def cancel_number(self, number):
        """Numbers cannot be released to cloud"""
        raise NotImplementedError

    def setup_number(self, number, inbound_sms_url=None,
                     inbound_voice_host=None):
        """ Numbers do not need to be set up """
        raise NotImplementedError

    def get_number(self, network):
        """ Numbers cannot be bought from provider"""
        raise NotImplementedError

    def send(self, to, from_, body, to_country=None, from_country=None):
        """Send an SMS to a Kannel interface.

        Returns:
           True if the message was accepted, False otherwise.
        """
        request = {
            'username' : self.username,
            'password' : self.password,
            'to' : to,
            'from' : from_,
            'text' : body
        }
        
        r = requests.get(self.outbound_sms_url, params=request)
        
        return (r.status_code >= 200 and r.status_code < 300)
