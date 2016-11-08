"""
Fake subscriber db that can be used for testing.

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

from core.subscriber.base import BaseSubscriber, SubscriberNotFound


class FakeSubscriberDB(BaseSubscriber):
    def __init__(self):
        super(FakeSubscriberDB, self).__init__()
        self._hlr = {}
        # initialise list of known subscribers
        for imsi, data in self.get_subscriber_states().items():
            self._add_sub(imsi, data['numbers'])

    def _add_sub(self, imsi, numbers, ip=None, port=None):
        self._hlr[imsi] = {
            'name': imsi,
            'ip': ip,
            'numbers': numbers,
            'port': port,
        }

    def add_subscriber_to_hlr(self, imsi, number, ip, port):
        """Adds a subscriber to the system."""
        self._add_sub(imsi, [number], ip, port)

    def delete_subscriber_from_hlr(self, imsi):
        """Removes a subscriber from the system."""
        try:
            del self._hlr[imsi]
        except KeyError:
            raise SubscriberNotFound(imsi)

    def get_subscribers(self, imsi=None):
        """Get subscribers, filter by IMSI if it's specified."""
        if imsi:
            return [(imsi, self._hlr[imsi])]
        return self._hlr.values()

    def add_number(self, imsi, number):
        """Associate another number with an IMSI.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            sub = self._hlr[imsi]
            sub.update('numbers', sub['numbers'] + [number])
        except KeyError:
            raise SubscriberNotFound(imsi)

    def delete_number(self, imsi, number):
        """Disassociate a number with an IMSI.

           Raises:
              SubscriberNotFound if imsi is not found
              ValueError if number doesn't belong to IMSI
                  or this is the sub's last number
        """
        sub = self._hlr.get(imsi)
        if not sub:
            raise SubscriberNotFound(imsi)
        numbers = sub['numbers']
        if len(sub < 2):
            raise ValueError("cannot remove %s from %s" % (number, imsi))
        new_numbers = [n for n in numbers if n != number]
        if len(new_numbers) == len(numbers):
            raise ValueError("%s not associated with %s" % (number, imsi))
        sub['numbers'] = new_numbers

    def get_caller_id(self, imsi):
        """Get a subscriber's caller_id.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            return self._hlr[imsi]['numbers'][0]
        except KeyError:
            raise SubscriberNotFound(imsi)
