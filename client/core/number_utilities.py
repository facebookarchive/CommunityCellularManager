# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

import re
import phonenumbers

from core.config_database import ConfigDB


CONF = ConfigDB()


def strip_number(number):
    """Strips the number down to just digits."""
    number = re.sub("[^0-9]", "", number)
    return number


def convert_to_e164(number, country="US"):
    return str(phonenumbers.format_number(
        phonenumbers.parse(number, country),
        phonenumbers.PhoneNumberFormat.E164))


def canonicalize(number):
    """Force a dialed number to have a country code.

    If the number arg has a leading + sign, the number_country's prefix will
    not be added to the front.
    """
    # TODO(matt): replace with ConfigDB.get once that is implemented.
    if 'number_country' in CONF:
        number_country = CONF['number_country']
    else:
        number_country = 'US'

    # The PH landline numbers that Nexmo gives us are considered improperly
    # formatted by libphonenumber. This hack puts them in a format
    # libphonenumber will handle correctly. See client issue #317 for details.
    if number_country == "PH" and number.startswith("63"):
        number = number[2:]

    try:
        canon = convert_to_e164(number, country=number_country)
    except phonenumbers.phonenumberutil.NumberParseException:
        canon = number
    if canon[0] == '+':
        canon = canon[1:]
    return str(canon)


def calling_code_from_country_code(country_code):
    """Gets the international calling code from a two letter country code."""
    data = {
        'BD': '+880', 'BE': '+32', 'BF': '+226', 'BG': '+359', 'BA': '+387',
        'BB': '+1-246', 'WF': '+681', 'BM': '+1-441', 'BN': '+673',
        'BO': '+591', 'BH': '+973', 'BI': '+257', 'BJ': '+229', 'BT': '+975',
        'JM': '+1-876', 'BV': '', 'BW': '+267', 'WS': '+685', 'BR': '+55',
        'BS': '+1-242', 'JE': '+44', 'BY': '+375', 'BZ': '+501', '': '+357',
        'RU': '+7', 'RW': '+250', 'RS': '+381', 'TL': '+670', 'RE': '+262',
        'TM': '+993', 'TJ': '+992', 'RO': '+40', 'TK': '+690', 'GW': '+245',
        'GU': '+1-671', 'GT': '+502', 'GS': '', 'GR': '+30', 'GQ': '+240',
        'GP': '+590', 'JP': '+81', 'GY': '+592', 'GG': '+44', 'GF': '+594',
        'GE': '+995', 'GD': '+1-473', 'GB': '+44', 'GA': '+241', 'GN': '+224',
        'GM': '+220', 'GL': '+299', 'GI': '+350', 'GH': '+233', 'OM': '+968',
        'TN': '+216', 'JO': '+962', 'TA': '+290', 'HR': '+385', 'HT': '+509',
        'HU': '+36', 'HK': '+852', 'HN': '+504', 'HM': '', 'VE': '+58',
        'PR': '+1-787 and 1-939', 'PS': '+970', 'PW': '+680', 'PT': '+351',
        'KN': '+1-869', 'PY': '+595', 'AI': '+1-264', 'PA': '+507', 'PF': '',
        'PG': '+675', 'PE': '+51', 'PK': '+92', 'PH': '+63', 'PN': '',
        'PL': '+48', 'PM': '+508', 'ZM': '+260', 'EH': '+212', 'EE': '+372',
        'EG': '+20', 'ZA': '+27', 'EC': '+593', 'IT': '+39', 'VN': '+84',
        'SB': '+677', 'ET': '+251', 'SO': '+252', 'ZW': '+263', 'KY': '+1-345',
        'ES': '+34', 'ER': '+291', 'ME': '+382', 'MD': '+373-533',
        'MG': '+261', 'MA': '+212', 'MC': '+377', 'UZ': '+998', 'MM': '+95',
        'ML': '+223', 'MO': '+853', 'MN': '+976', 'MH': '+692', 'MK': '+389',
        'MU': '+230', 'MT': '+356', 'MW': '+265', 'MV': '+960', 'MQ': '+596',
        'MP': '+1-670', 'MS': '+1-664', 'MR': '+222', 'IM': '+44',
        'UG': '+256', 'MY': '+60', 'MX': '+52', 'IL': '+972', 'FR': '+33',
        'AW': '+297', 'SH': '+290', 'AX': '+358-18', 'SJ': '+47', 'FI': '+358',
        'FJ': '+679', 'FK': '+500', 'FM': '+691', 'FO': '+298', 'NI': '+505',
        'NL': '+31', 'NO': '+47', 'NA': '+264', 'VU': '+678', 'NC': '+687',
        'NE': '+227', 'NF': '+672', 'NG': '+234', 'NZ': '+64', 'NP': '+977',
        'NR': '+674', 'NU': '+683', 'CK': '+682', 'CI': '+225', 'CH': '+41',
        'CO': '+57', 'CN': '+86', 'CM': '+237', 'CL': '+56', 'CC': '+61',
        'CA': '+1', 'CG': '+242', 'CF': '+236', 'CD': '+243', 'CZ': '+420',
        'CY': '+90-392', 'CX': '+61', 'CS': '+381', 'CR': '+506', 'CV': '+238',
        'CU': '+53', 'SZ': '+268', 'SY': '+963', 'KG': '+996', 'KE': '+254',
        'SR': '+597', 'KI': '+686', 'KH': '+855', 'SV': '+503', 'KM': '+269',
        'ST': '+239', 'SK': '+421', 'KR': '+82', 'SI': '+386', 'KP': '+850',
        'KW': '+965', 'SN': '+221', 'SM': '+378', 'SL': '+232', 'SC': '+248',
        'KZ': '+7', 'SA': '+966', 'SG': '+65', 'SE': '+46', 'SD': '+249',
        'DO': '+1-809 and 1-829', 'DM': '+1-767', 'DJ': '+253', 'DK': '+45',
        'VG': '+1-284', 'DE': '+49', 'YE': '+967', 'DZ': '+213', 'US': '+1',
        'UY': '+598', 'YT': '+262', 'UM': '', 'LB': '+961', 'LC': '+1-758',
        'LA': '+856', 'TV': '+688', 'TW': '+886', 'TT': '+1-868', 'TR': '+90',
        'LK': '+94', 'LI': '+423', 'LV': '+371', 'TO': '+676', 'LT': '+370',
        'LU': '+352', 'LR': '+231', 'LS': '+266', 'TH': '+66', 'TF': '',
        'TG': '+228', 'TD': '+235', 'TC': '+1-649', 'LY': '+218', 'VA': '+379',
        'AC': '+247', 'VC': '+1-784', 'AE': '+971', 'AD': '+376',
        'AG': '+1-268', 'AF': '+93', 'IQ': '+964', 'VI': '+1-340',
        'IS': '+354', 'IR': '+98', 'AM': '+374', 'AL': '+355', 'AO': '+244',
        'AN': '+599', 'AQ': '', 'AS': '+1-684', 'AR': '+54', 'AU': '',
        'AT': '+43', 'IO': '+246', 'IN': '+91', 'TZ': '+255', 'AZ': '+374-97',
        'IE': '+353', 'ID': '+62', 'UA': '+380', 'QA': '+974', 'MZ': '+258'
    }
    return strip_number(data[country_code])
