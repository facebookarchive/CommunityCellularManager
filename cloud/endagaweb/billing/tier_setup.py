"""Utility methods for setting up billing tiers.

Primarily called by the 0035 data migration.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import xlrd
import yaml


def xls_to_array(filepath, worksheet_name):
    """Converts an XLS file with headers to a dict."""
    workbook = xlrd.open_workbook(filepath)
    worksheet = workbook.sheet_by_name(worksheet_name)
    data = []
    keys = [v.value for v in worksheet.row(0)]
    for row_number in range(worksheet.nrows):
        if row_number == 0:
            continue
        row_data = {}
        for col_number, cell in enumerate(worksheet.row(row_number)):
            row_data[keys[col_number]] = cell.value
        data.append(row_data)
    return data


def create_tier_data():
    """Creating data for Destinations, DestinationGroups and BillingTiers.

    Reads endagaweb/fixtures/billing-tiers.yml and pricing.xls. The
    two files determine the setup of the models.  Destinations and DG models
    are shared amongst the Networks.

    This will just return metadata that should be actually applied to models
    in the data migration script.  This doesn't touch models because the same
    default BTs have to be setup for every Network and it's easier to test just
    this method.

    This will extend the data found in config file billing-tiers.yml.  We will
    scan the rows of the pricing spreadsheet (pricing.xls) to create
    Destinations and, based on that config file, assign those Destinations to
    DestinationGroups.

    The sms_price_ceiling_euro and voice_price_ceiling_euro keys are now
    deprecated.  These were formerly used to determine which countries would
    end up in which Tier, but that is now manually specified.

    This method returns an array of dicts, one for each billing tier:
    {
        'name': 'Off-Network Sending, Tier A',
        'directionality': 'off_network_send',
        'sms_price_ceiling_euro': 0.008,
        'voice_price_ceiling_euro': 0.02,
        'cost_to_operator_per_sms': 1000,
        'cost_to_operator_per_min': 2000,
        'cost_to_subscriber_per_sms': 1000,
        'cost_to_subscriber_per_min': 2000,
        'destinations': [{
          'country_code': 'AF',
          'country_name': 'Afghanistan',
          'prefix': '93',
          'price_per_message_euro': 0.038,
          'price_per_min_euro': 0.189,
        }, {
          'country_code': 'BG',
          'country_name': 'Bulgaria',
          'prefix': '359',
          'price_per_message_euro': 0.05,
          'price_per_min_euro': 0.1745,
        }]
    }
    """
    with open('endagaweb/fixtures/billing-tiers.yml') as yaml_file:
        tier_data = yaml.safe_load(yaml_file)
    # First initialize subscriber prices to match the operator costs.  The only
    # difference is in the subscriber prices for on-network sending.  We want
    # the subscriber prices to be nonzero so we don't overload the network with
    # local traffic.
    for tier in tier_data:
        if tier['directionality'] == 'on_network_send':
            tier['cost_to_subscriber_per_sms'] = 200
            tier['cost_to_subscriber_per_min'] = 200
        else:
            tier['cost_to_subscriber_per_sms'] = (
                tier['cost_to_operator_per_sms'])
            tier['cost_to_subscriber_per_min'] = (
                tier['cost_to_operator_per_min'])
    # Read prefix pricing data from the spreadsheet.
    sms_xls_data = xls_to_array('endagaweb/fixtures/pricing.xls',
                                'Outbound SMS')
    voice_xls_data = xls_to_array('endagaweb/fixtures/pricing.xls',
                                  'Outbound Voice')
    # Boil this down such that we have one sms and voice price for each prefix.
    sms_prefixes = set([d['Prefix'] for d in sms_xls_data])
    voice_prefixes = set([d['Prefix'] for d in voice_xls_data])
    all_prefixes = sms_prefixes.union(voice_prefixes)
    all_prefix_data = []
    for prefix in all_prefixes:
        prefix_data = {
            'prefix': prefix
        }
        voice_data = [row for row in voice_xls_data if row['Prefix'] == prefix]
        # We have to make some manual adjustments to the country name.
        if prefix == '1':
            prefix_data['country_name'] = 'US and Canada'
        elif prefix == '7':
            prefix_data['country_name'] = 'Russia and Kazakhstan'
        else:
            prefix_data['country_name'] = voice_data[0]['Country Name']
        prefix_data['country_code'] = voice_data[0]['Country Code']
        voice_prices = [d['Price (EUR) / min'] for d in voice_data]
        prefix_data['price_per_min_euro'] = max(voice_prices)
        # Capture SMS pricing data.  Note that some prefixes that showed up in
        # the voice pricing sheet will not appear here (see the comment above).
        sms_data = [row for row in sms_xls_data if row['Prefix'] == prefix]
        sms_prices = [d['Price (EUR) / message'] for d in sms_data]
        if not sms_prices:
            prefix_data['price_per_message_euro'] = 0
        else:
            prefix_data['price_per_message_euro'] = max(sms_prices)
        all_prefix_data.append(prefix_data)
    # Now put each prefix into a billing tier based on the config file.
    processed_prefixes = []
    for tier in tier_data:
        if tier['directionality'] != 'off_network_send':
            continue
        tier['destinations'] = []
        for prefix_data in all_prefix_data:
            if prefix_data in processed_prefixes:
                continue
            if prefix_data['country_code'] in tier['countries']:
                tier['destinations'].append(prefix_data)
                processed_prefixes.append(prefix_data)
    return tier_data
