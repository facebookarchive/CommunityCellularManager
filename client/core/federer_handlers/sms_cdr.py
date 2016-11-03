"""SMS "CDR" handlers for the federer server.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import web

from core import billing
from core import events
from core.subscriber import subscriber
from core.exceptions import SubscriberNotFound

class smscdr(object):
    """Handles SMS CDRs."""

    def POST(self):
        """Handles POST requests."""
        data = web.input()
        if ('from_name' not in data or 'service_type' not in data or
                'destination' not in data):
            raise web.BadRequest()
        # Process the CDR data.
        cost_in_credits = billing.get_sms_cost(
            data.service_type, destination_number=data.destination)
        try:
            old_balance = subscriber.get_account_balance(data.from_name)
            subscriber.subtract_credit(data.from_name, str(cost_in_credits))
        except SubscriberNotFound:
            # The subscriber does not exist yet but has sent an SMS
            if data.service_type == 'free_sms':
                # But that is OK for a free service like provisioning
                old_balance = 0
            else:
                raise
        reason = "SMS sent to %s (%s)" % (data.destination, data.service_type)
        events.create_sms_event(
            data.from_name, old_balance, cost_in_credits, reason,
            data.destination, from_imsi=data.from_name,
            from_number=data.from_number)
        # If this was an in-network event, find the cost for the recipient.  We
        # can lookup the recipient by data.destination (the "to number").
        if 'local' in data.service_type:
            recipient_imsi = subscriber.get_imsi_from_number(data.destination)
            old_balance = subscriber.get_account_balance(recipient_imsi)
            cost_in_credits = billing.get_sms_cost(
                'local_recv_sms', destination_number=data.destination)
            subscriber.subtract_credit(recipient_imsi, str(cost_in_credits))
            reason = "SMS received from %s (local_recv_sms)" % data.from_name
            events.create_sms_event(
                recipient_imsi, old_balance, cost_in_credits, reason,
                data.destination, from_imsi=data.from_name,
                from_number=data.from_number)
        # Return 200 OK.
        headers = {
            'Content-type': 'text/plain'
        }
        raise web.OK(None, headers)
