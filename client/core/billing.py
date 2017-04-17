"""Credit management utilities.

Note that subscriber credit operations are handled in core.subscriber.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""





import math
import os

from ccm.common import logger
from core import config_database


config_db = config_database.ConfigDB()
# In our CI system, Postgres credentials are stored in env vars.
PG_USER = os.environ.get('PG_USER', 'endaga')
PG_PASSWORD = os.environ.get('PG_PASSWORD', 'endaga')

def round_to_billable_unit(billsec, rate_per_min, free_seconds=0, billable_unit=1):
    """
    Round the call up to the billable units
      round_to_billable_unit(5, 60) = 5
      round_to_billable_unit(5, 60, 10) = 0
      round_to_billable_unit(5, 60, 0, 30) = 30
      round_to_billable_unit(5, 60, 0, 60) = 60
      round_to_billable_unit(61, 60, 0, 60) = 120

    Args:
      billsec: the number of billable seconds
      rate_per_min: the tariff per minute, in the internal currency representation
      free_seconds: the allotment of free seconds
      billable_unit: the minimum billable amount in seconds
        (e.g., bill for every 30 seconds)


    Returns:
      integer cost
    """
    # Account for "free seconds"
    billsec = max(0, int(billsec) - int(free_seconds))

    # Round up raw seconds to seconds of billable units
    units = int(billsec/billable_unit) + (billsec % billable_unit > 0)
    normalized_billsec = units * billable_unit

    # Determine the cost given per-min rate
    return int(normalized_billsec * rate_per_min/60.0)

def round_up_to_nearest_100(raw_cost):
    """

    Round up to the max of 0 or the next value of 100.  E.g.:
      round_to_nearest_100(5) = 100

    Args:
      raw_cost: the raw unrounded cost

    Returns:
      integer cost
    """
    return max(0, int(math.ceil(raw_cost / 100.0)) * 100)


def get_prefix_from_number(number):
    """Find the prefix associated with a number.

    We need to find the prefix that best matches the given number.  For
    instance, a number that starts with 1876 should match to Jamaica (prefix
    1876) and not the US and Canada (prefix 1).  For a similar method on the
    operator-billing side of things, see
    endagaweb.models.Network.calculate_operator_cost.

    We will probe the ConfigDB to determine what prefixes are available.

    Args:
      number: a destination number

    Returns:
      the matching prefix
    """
    # Get all price keys in memory for querying.
    price_keys = [d[0] for d in config_db._connector.exec_and_fetch(
        "SELECT key FROM endaga_config WHERE key LIKE"
        " 'prices.off_network_send.%.cost_to_subscriber_per_min';")]

    # The longest prefix available is four digits, so truncate the number.
    possible_prefix = number[0:5]
    while possible_prefix:
        key = ('prices.off_network_send.%s.cost_to_subscriber_per_min' %
               possible_prefix)
        if key in price_keys:
            return possible_prefix
        else:
            # Pop off the last number and query again for a shorter prefix.
            possible_prefix = possible_prefix[0:-1]

# Other legacy service types need to be re-mapped to the new billing tier
# structure.
def convert_legacy_service_type(service_type):
    if 'local_recv' in service_type:
        return 'on_network_receive'
    elif 'local' in service_type:
        return 'on_network_send'
    elif 'incoming' in service_type:
        return 'off_network_receive'
    elif 'outside' in service_type:
        return 'off_network_send'
    return service_type

def get_service_tariff(service_type, activity_type, destination_number=''):
    """Get the tariff for the given service type.

    Prices are stored in the ConfigDB and are of the form
    'prices.on_network_send.cost_to_subscriber_per_min' or, if it's an outbound
    key, the prefix is included:
      'prices.off_network_send.56.cost_to_subscriber_per_sms'

    Args:
      service_type: one of off_network_send, off_network_receive,
                    on_network_send, off_network_receive, free or error
      activity_type: call or sms
      destination_number: the number we're calling or texting

    Returns:
      integer value of service tariff if the type exists
      None if no such type.
    """
    # Certain service types are free.
    if 'free' in service_type or 'error' in service_type:
        return 0

    service_type = convert_legacy_service_type(service_type)

    # Set the cost key suffix.
    if activity_type == 'call':
        cost_key = 'cost_to_subscriber_per_min'
    elif activity_type == 'sms':
        cost_key = 'cost_to_subscriber_per_sms'
    # Lookup the prefix if a destination number is set.
    if destination_number and service_type == 'off_network_send':
        prefix = get_prefix_from_number(destination_number)
        key = 'prices.%s.%s.%s' % (service_type, prefix, cost_key)
    else:
        key = 'prices.%s.%s' % (service_type, cost_key)
    # Finally lookup the actual cost.
    try:
        return int(config_db[key])
    except KeyError:
        logger.error("get_service_tariff lookup failed for key: %s" % key)
        return 0

def get_service_billable_unit(service_type, destination_number):
    """ Gets the billable unit for a service type and destination. Default is 1
    second (this is used when we don't have a matching billable unit).
    """
    # Certain service types are free.
    if 'free' in service_type or 'error' in service_type:
        return 1

    service_type = convert_legacy_service_type(service_type)

    prefix = get_prefix_from_number(destination_number)
    if service_type == "off_network_send":
        key = 'prices.%s.%s.billable_unit' % (service_type, prefix)
    else:
        key = 'prices.%s.billable_unit' % (service_type)

    try:
        return int(config_db[key])
    except KeyError:
        logger.error("get_service_billable_unit lookup failed for key: %s" % key)
        return 1

def get_call_cost(billsec, service_type, destination_number=''):
    """Get the cost of a call.

    Args:
      billsec: the call's billable duration
      service_type: the type of call
      destination_number: the number we're calling

    Returns:
      cost of call
    """
    rate_per_min = get_service_tariff(
        service_type, 'call', destination_number=destination_number)
    free_seconds = int(config_db['free_seconds'])
    billable_unit = get_service_billable_unit(
        service_type, destination_number)
    return round_up_to_nearest_100(
        round_to_billable_unit(billsec, rate_per_min,
                               free_seconds, billable_unit))


def get_sms_cost(service_type, destination_number=''):
    """Get the cost of an SMS.

    Args:
      service_type: the type of SMS
      destination_number: the number we're sending a text to

    Returns:
      cost of call
    """
    return get_service_tariff(service_type, 'sms',
                              destination_number=destination_number)

def get_seconds_available(account_balance, service_type,
                          destination_number, max=60*60*48):
    cost_per_min = get_service_tariff(service_type, 'call', destination_number)
    billable_unit = get_service_billable_unit(service_type, destination_number)
    sec_allowed = int(account_balance / (cost_per_min/60.))
    units_allowed = sec_allowed / billable_unit
    return units_allowed * billable_unit


def process_prices(pricing_data, config_db):
    """Processes incoming price data from the checkin response.

    Saves these prices in the ConfigDB, creating keys if needed.

    Args:
    pricing_data: a list of dicts.  Each dict is either an on-network
    receive tier, an on-network send tier, an off-network receive
    tier or an off-network send tier.  There are many off-network
    send tiers, one for each prefix (country).  But there is only one
    of the other three classes of tiers.  All costs are given in
    millicents.  For example:
    {
    'directionality': 'off_network_send',
    'prefix': '53',
    'country_name': 'Finland',
    'country_code': 'FI',
    'cost_to_subscriber_per_sms': 5000,
    'cost_to_subscriber_per_min': 2000,
    'billable_unit': 1,
    }, {
    'directionality': 'off_network_receive',
    'cost_to_subscriber_per_sms': 100,
    'cost_to_subscriber_per_min': 200,
    'billable_unit': 1,
    }, {
    'directionality': 'on_network_send',
    'cost_to_subscriber_per_sms': 25,
    'cost_to_subscriber_per_min': 50,
    'billable_unit': 1,
    }, {
    'directionality': 'on_network_receive',
    'cost_to_subscriber_per_sms': 10,
    'cost_to_subscriber_per_min': 20,
    'billable_unit': 1,
    }
    """
    for price_group in pricing_data:
        # Set the config db keys.
        prefixless_keys = ('off_network_receive', 'on_network_receive',
                           'on_network_send')
        if price_group['directionality'] in prefixless_keys:
            sms_key = ('prices.%s.cost_to_subscriber_per_sms' %
                       (price_group['directionality'], ))
            call_key = ('prices.%s.cost_to_subscriber_per_min' %
                        (price_group['directionality'], ))
            billable_unit_key = ('prices.%s.billable_unit' %
                                 (price_group['directionality'], ))
        elif price_group['directionality'] == 'off_network_send':
            sms_key = ('prices.%s.%s.cost_to_subscriber_per_sms' %
                       ('off_network_send', price_group['prefix']))
            call_key = ('prices.%s.%s.cost_to_subscriber_per_min' %
                        ('off_network_send', price_group['prefix']))
            billable_unit_key = ('prices.%s.%s.billable_unit' %
                                 ('off_network_send', price_group['prefix']))
        # Get the actual values specified in the checkin response data.
        sms_new_value = price_group['cost_to_subscriber_per_sms']
        call_new_value = price_group['cost_to_subscriber_per_min']

        # Legacy cloud responses may not include this,
        # so we default to 1
        billable_unit_new_val = price_group.get('billable_unit', 1)
        # Add to the config db if necessary.
        for key, new_value in [
                (sms_key, sms_new_value),
                (call_key, call_new_value),
                (billable_unit_key, billable_unit_new_val)]:
            old_value = config_db.get(key)
            if old_value is None:
                logger.notice("adding key: %s -> %s" %
                              (key, new_value))
                config_db[key] = new_value
            else:
                if config_db._ducktype(new_value) != old_value:
                    logger.notice("changing key: %s -> %s (was %s)" %
                                  (key, new_value, old_value))
                    config_db[key] = new_value
