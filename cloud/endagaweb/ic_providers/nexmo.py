"""Client to libpynexmo.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import random
import urllib

from nexmomessage import NexmoMessage

from endagaweb.models import Number
from endagaweb.ic_providers import provider


class NexmoProvider(provider.InterconnectProvider):
    """The Nexmo client -- interfaces with libpynexmo (nexmomessage)."""
    def __init__(self, nexmo_acct_sid, nexmo_auth_token, inbound_sms_url, 
                 outbound_sms_url, inbound_voice_host, country='SE'):
        self.username = nexmo_acct_sid
        self.password = nexmo_auth_token
        self.inbound_sms_url = inbound_sms_url
        #should be ignored
        self.outbound_sms_url = outbound_sms_url
        self.inbound_voice_host = inbound_voice_host
        self.country = country

    def get_existing_numbers(self, ignore_country=True):
        """Gets all numbers purchased by this user

        TODO(matt): better comments on this one.
        """
        total = None
        size = 100
        index = 1
        seen = 0
        # First request finds out how many there are.
        req = {
            'password': self.password,
            'username': self.username,
            'type': 'numbers',
            'size': size
        }
        res = NexmoMessage(req).send_request()
        nums = []
        for r in res['numbers']:
            seen += 1
            if (ignore_country or r['country'] == self.country):
                nums.append(r['msisdn'])
        total = int(res['count'])

        while seen < total:
            index += 1
            req = {
                'password': self.password,
                'username': self.username,
                'type': 'numbers',
                'size': size,
                'index': index
            }
            res = NexmoMessage(req).send_request()
            for r in res['numbers']:
                seen += 1
                if (ignore_country or r['country'] == self.country):
                    nums.append(r['msisdn'])

        return nums

    def get_number_info(self, number, count=10):
        """Get info on a number."""
        req = {
            'password': self.password,
            'username': self.username,
            'type': 'numbers',
            'pattern': number,
            'size': count
        }
        res = NexmoMessage(req).send_request()
        # TODO(matt): not sure I understand what's happening below..  It's hard
        #             to figure out without knowing the Nexmo response.  Seems
        #             to be duplicating 'r' into 'nums'.  Maybe it's making it
        #             possible to lookup by number?
        nums = {}
        for r in res['numbers']:
            nums[r['msisdn']] = r
        return nums

    def search_numbers(self, features="SMS,VOICE"):
        """Search for available numbers from Nexmo in self.country."""
        req = {
            'password': self.password,
            'username': self.username,
            'type': 'search',
            'country': self.country,
            'features': features
        }
        res = NexmoMessage(req).send_request()
        if 'numbers' not in res or len(res['numbers']) == 0:
            raise ValueError("No numbers available.")
        # May need to filter based on some desired properties, like mobile.
        return random.choice(res['numbers'])['msisdn']

    def buy_number(self, number):
        """Buy a number from Nexmo."""
        req = {
            'password': self.password,
            'username': self.username,
            'type': 'buy',
            'country': self.country,
            'msisdn': number
        }
        res = NexmoMessage(req).send_request()
        print 'buying number %s' % number
        return res['code'] == 200

    def cancel_number(self, number):
        """Release a number back to Nexmo."""
        req = {
            'username': self.username,
            'password': self.password,
            'type': 'cancel',
            'country': self.country,
            'msisdn': number
        }
        res = NexmoMessage(req).send_request()
        print 'releasing number %s' % number
        return res['code'] == 200

    def setup_number(self, number, inbound_sms_url=None,
                     inbound_voice_host=None):
        """Sets up a number with Nexmo.

        TODO(matt): get some clarity on what this method does..

        Args:
            number: the number to setup
            inbound_sms_url: the callback to hit for inbound SMS
            inbound_voice_host: the callback to hit for inbound voice
        """
        # Use provider defaults if values not specified in the method call.
        if not inbound_sms_url:
            inbound_sms_url = self.inbound_sms_url
        if not inbound_voice_host:
            inbound_voice_host = self.inbound_voice_host

        voice_callback_value = '%s@%s' % (number, inbound_voice_host)
        request = {
            'password': self.password,
            'username': self.username,
            'type': 'update',
            'country': self.country,
            'msisdn': number,
            'moHttpUrl': urllib.quote_plus(inbound_sms_url),
            'voiceCallbackType': 'sip',
            'voiceCallbackValue': urllib.quote_plus(voice_callback_value)
        }
        res = NexmoMessage(request).send_request()
        print 'setting up number %s' % number
        return res['code'] == 200

    def get_number(self, network):
        """Get a number from this provider. As long as we always associate the
        new number to a user immediately upon purchase, we don't need to worry
        about not-in-use-numbers.

        Note: we don't have any test mode specific code here, because the
        underlying methods this relies on all have proper test behavior. i.e.,
        buy number is stubbed, search_numbers, is stubbed, etc. This way we can
        rely on the side effects this function normally has... screaming for a
        refactor.
        """
        if self.country == "PH":
            # we only have voice numbers for PH
            target = self.search_numbers(features="VOICE")
        else:
            target = self.search_numbers()
        print "Target is %s" % target
        if self.buy_number(target):
            print "Bought %s" % target
            n = Number(number=str(target), state="available", network=network,
                       kind="number.nexmo.monthly")
            n.country_id = self.country
            n.save()
            n.charge()
            if self.setup_number(target):
                print "Set up %s" % target
                # TODO: We should have number in "out of service" state before
                #       setup, then set it to available here, in case setup
                #       fails.
                return int(target)
            else:
                raise ValueError("Failed to set up number from Nexmo!")
        else:
            raise ValueError("Failed to buy number from Nexmo!")

    def send(self, to, from_, body, to_country=None, from_country=None):
        """Send an SMS to Nexmo.

        Returns:
           True if the message was accepted, False otherwise.
        """
        # The Nexmo client can't send an empty string, so instead send a space.
        if len(body) == 0:
            body = ' '

        msg = {
            'username': self.username,
            'password': self.password,
            'reqtype': 'json',
            'from': from_,
            'to': to
        }
        sms = NexmoMessage(msg)
        sms.set_text_info(body)
        res = sms.send_request()
        return (res['message-count'] == '1' and
                res['messages'][0]['status'] == '0')
