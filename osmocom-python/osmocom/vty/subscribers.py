"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import re
import sqlite3

from .base import BaseVTY
from .util import parse_imsi, format_imsi

class Subscribers(BaseVTY):

    def __init__(self, host='127.0.0.1', port=4242, hlr_loc='/home/vagrant/osmocom/hlr.sqlite3', timeout=None):
        super(Subscribers, self).__init__('OpenBSC', host, port, timeout)
        self.hlr_loc = hlr_loc
        self.PARSE_SHOW= [
            re.compile('ID: (?P<id>\d+), Authorized: (?P<authorized>\d+)'),
            re.compile('Extension: (?P<extension>\d+)'),
            re.compile('Name: \'(?P<name>.+)\''),
            re.compile('LAC: (?P<lac>\d+)/0x(?P<lac_hex>[0-9a-fA-F]+)'),
            re.compile('IMSI: (?P<imsi>\d{13,15})'),
            re.compile('Expiration Time: (?P<expiration>[^\r]+)'),
            re.compile('Paging: (?P<paging>(is|not)) paging Requests: (?P<requests>\d+)'),
            re.compile('Use count: (?P<use_count>\d+)')]

    def camped_subscribers(self, access_period=0, auth=1):
        """Gets all camped subscribers from the HLR.

        Args:
          access_period: fetches all entries with ACCESS < access_period
                             (default=0 filter off)
          auth: fetches all entries with AUTH = auth
                  Unauthorized = 0
                  Authorized by registrar (default) = 1

        Returns a list subscriber objects with the following values:
           IMSI, TMSI, IMEI, AUTH, CREATED, ACCESSED, TMSI_ASSIGNED
       """
        con = sqlite3.connect(self.hlr_loc)
        con.row_factory = sqlite3.Row
        query = ("SELECT s.imsi as IMSI,"
                    "s.tmsi as TMSI,"
                    "e.imei as IMEI,"
                    "s.authorized as AUTH,"
                    "s.created as CREATED,"
                    "strftime('%s', s.updated) as ACCESSED,"
                    "s.tmsi IS NOT NULL as TMSI_ASSIGNED "
                "FROM Subscriber s,"
                    "EquipmentWatch ew,"
                    "Equipment e "
                "WHERE s.id = ew.subscriber_id "
                    "AND ew.equipment_id = e.id "
                    "AND AUTH = " + str(int(auth)))
        if access_period > 0:
            query += " AND strftime('%s','now') - ACCESSED < " + str(int(access_period))

        subscribers = []
        for row in con.execute(query):
            subscriber = dict(list(zip(list(row.keys()), row)))

            # Ensure that the IMSI is 15 digits
            subscriber['IMSI'] = format_imsi(subscriber['IMSI'])

            subscribers.append(subscriber)
        con.close()
        return subscribers


    def create(self, imsi):
        """Create a subscriber with a given IMSI.

        BUGS: on x86 if a subscriber already exists, it will crash osmo-nitb.
        """
        imsi = parse_imsi(imsi)
        resp = self.sendrecv('subscriber create imsi %s' % imsi)
        return self._parse_show(resp)

    def delete(self, imsi):
        """Delete a subscriber"""
        imsi = parse_imsi(imsi)
        with self.enable_mode():
            resp = self.sendrecv('subscriber imsi %s delete' % imsi)
        if 'No subscriber found' in resp:
            raise ValueError(resp)
        return resp

    def sms(self, imsi_dest, imsi_src, body):
        """Send an sms to a subscriber.
        Note that the source imsi must  be a valid subscriber.
        """
        imsi_dest = parse_imsi(imsi_dest)
        imsi_src = parse_imsi(imsi_src)
        return self.sendrecv('subscriber imsi %s sms sender imsi %s send %s' %
            (imsi_dest, imsi_src, body))

    def set_extension(self, imsi, extension):
        """Set the extension of a subscriber."""
        return self.__set(imsi, 'extension', extension)

    def set_name(self, imsi, name):
        """Set the name of a subscriber."""
        return self.__set(imsi, 'name', name)

    def set_authorized(self, imsi, authorized):
        """Set the authorization of a subscriber."""
        return self.__set(imsi, 'authorized', authorized)

    def show(self, key, value):
        """Retreives data returned when issuing the show command
        on the VTTY as a dictionary with data entries corresponding
        to the named regex matching groups in `self.PARSE_SHOW`

        You can lookup subscribers by extension, imsi, id, or tmsi

        The prefix 'IMSI' is stripped from IMSIs
        """
        if key not in ['extension', 'imsi', 'id', 'tmsi']:
            raise KeyError('invalid lookup key')
        if key == 'imsi':
            value = parse_imsi(value)
        resp = self.sendrecv('show subscriber %s %s' % (key, value))
        if 'No subscriber found' in resp:
            raise ValueError(resp)
        data = self._parse_show(resp)

        # Ensure that the IMSI is 15 digits
        data['imsi'] = format_imsi(data['imsi'])

        return data

    def __set(self, imsi, field, value):
        """Generic method for issuing set commands.
        Handles entering enabled mode for updating the HLR.
        """
        imsi = parse_imsi(imsi)
        with self.enable_mode():
            resp = self.sendrecv('subscriber imsi %s %s %s' % (imsi, field, value))
        if '%' in resp:
            raise ValueError(resp)
        return resp
