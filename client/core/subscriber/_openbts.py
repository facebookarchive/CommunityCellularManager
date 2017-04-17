# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.





import sys

import openbts
from openbts.exceptions import InvalidRequestError

from core import number_utilities
from core.config_database import ConfigDB
from core.subscriber.base import BaseSubscriber, SubscriberNotFound
from core.exceptions import BSSError

class OpenBTSSubscriber(BaseSubscriber):
    def __init__(self):
        super(OpenBTSSubscriber, self).__init__()
        self.conf = ConfigDB()
        self.sip_auth_serve = openbts.components.SIPAuthServe(
            socket_timeout=self.conf['bss_timeout'],
            cli_timeout=self.conf['bss_timeout'])

    def add_subscriber_to_hlr(self, imsi, number, ip, port):
        """Adds a subscriber to the system."""
        try:
            return self.sip_auth_serve.create_subscriber(imsi, number, ip, port)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def delete_subscriber_from_hlr(self, imsi):
        """Removes a subscriber from the system."""
        try:
            return self.sip_auth_serve.delete_subscriber(imsi)
        except InvalidRequestError:
            raise SubscriberNotFound(imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_subscribers(self, imsi=None):
        """Get subscribers, filter by IMSI if it's specified."""
        try:
            return self.sip_auth_serve.get_subscribers(imsi=imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def add_number(self, imsi, number):
        """Associate another number with an IMSI.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            return self.sip_auth_serve.add_number(imsi, number)
        except InvalidRequestError:
            raise SubscriberNotFound(imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def delete_number(self, imsi, number):
        """Disassociate a number with an IMSI.

           Raises:
              SubscriberNotFound if imsi is not found
              ValueError if number doesn't belong to IMSI
                  or this is the sub's last number
        """
        try:
            self.get_caller_id(imsi)  # raise InvalidRequestError when sub doesnt exist
            return self.sip_auth_serve.delete_number(imsi, number)
        except InvalidRequestError:
            raise SubscriberNotFound(imsi)
        except ValueError as e:
            # this is raised when a number doesn't belong to a sub
            # also raised when this is the subs last number
            raise e
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_caller_id(self, imsi):
        """Get a subscriber's caller_id.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            return self.sip_auth_serve.get_caller_id(imsi)
        except InvalidRequestError:
            raise SubscriberNotFound(imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_ip(self, imsi):
        """Get a subscriber's IP address.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            return self.sip_auth_serve.get_openbts_ipaddr(imsi)
        except InvalidRequestError:
            raise SubscriberNotFound(imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_port(self, imsi):
        """Get a subscriber's port.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            return self.sip_auth_serve.get_openbts_port(imsi)
        except InvalidRequestError:
            raise SubscriberNotFound(imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_numbers_from_imsi(self, imsi):
        """Gets numbers associated with a subscriber.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        try:
            return self.sip_auth_serve.get_numbers(imsi)
        except InvalidRequestError:
            raise SubscriberNotFound(imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_imsi_from_number(self, number, canonicalize=True):
        """Gets the IMSI associated with a number.

           Raises:
              SubscriberNotFound if imsi is not found
        """
        if canonicalize:
            number = number_utilities.canonicalize(number)
        try:
            return self.sip_auth_serve.get_imsi_from_number(number)
        except InvalidRequestError:
            raise SubscriberNotFound('MSISDN %s' % number)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_username_from_imsi(self, imsi):
        """Gets the SIP name of the subscriber

           Raises:
              SubscriberNotFound if imsi is not found
        """
        self.get_caller_id(imsi) # assert sub exists
        return imsi

    def get_imsi_from_username(self, username):
        """Get the IMSI from the SIP name

           This doesn't raise exceptions because it cannot fail or the dialplan
           chatplan will fail
        """
        return username

    def is_authed(self, imsi):
        """Returns True if the subscriber is provisioned

        In openbts, a user is provisioned once an extension is assigned
        """
        try:
            return len(self.get_numbers_from_imsi(imsi)) > 0
        except InvalidRequestError:
            return False
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)

    def get_gprs_usage(self, target_imsi=None):
        """Get all available GPRS data, or that of a specific IMSI (experimental).

        Will return a dict of the form: {
          'ipaddr': '192.168.99.1',
          'downloaded_bytes': 200,
          'uploaded_bytes': 100,
        }

        Or, if no IMSI is specified, multiple dicts like the one above will be
        returned as part of a larger dict, keyed by IMSI.

        Args:
          target_imsi: the subsciber-of-interest
        """
        try:
            res = self.sip_auth_serve.get_gprs_usage(target_imsi)
        except Exception:
            exc_type, exc_value, exc_trace = sys.exc_info()
            raise BSSError("%s: %s" % (exc_type, exc_value)).with_traceback(exc_trace)
        if not res:
            raise SubscriberNotFound(target_imsi)
        return res
