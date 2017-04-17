"""
Fake subscriber db that can be used for testing.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""






from core import number_utilities
from core.subscriber.base import BaseSubscriber, SubscriberNotFound


class FakeSubscriberDB(BaseSubscriber):
    def __init__(self):
        super(FakeSubscriberDB, self).__init__()
        self._hlr = {}
        # initialise list of known subscribers
        for imsi, data in list(self.get_subscriber_states().items()):
            self._add_sub(imsi, data['numbers'])

    def _add_sub(self, imsi, numbers, ip=None, port=None):
        self._hlr[imsi] = {
            "name": imsi,
            "ip": ip,
            "numbers": numbers,
            "port": port,
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
        """Gets subscribers, optionally filtering by IMSI.

        Args:
        imsi: the IMSI to search by

        Returns:
        an empty array if no subscribers match the query, or an array of
        subscriber dicts, themselves of the form: {
            'name': 'IMSI000123',
            'ip': '127.0.0.1',
            'port': '8888',
            'numbers': ['5551234', '5556789'],
        }
        """
        if imsi:
            # per docstring, return empty list if IMSI not found
            sub = self._hlr.get(imsi)
            return [sub] if sub else []
        return list(self._hlr.values())

    def add_number(self, imsi, number):
        """Associate another number with an IMSI.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            sub = self._hlr[imsi]
            sub['numbers'] = sub['numbers'] + [number]
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

    def get_imsi_from_number(self, number, canonicalize=True):
        """Gets the IMSI associated with a number."""
        if canonicalize:
            number = number_utilities.canonicalize(number)
        for imsi, data in list(self._hlr.items()):
            if number in data['numbers']:
                return imsi
        return None

    def get_imsi_from_username(self, username):
        """
        Get the IMSI from the SIP name.

        FakeBTS uses IMSI as username, so this is trivial.
        """
        return username
