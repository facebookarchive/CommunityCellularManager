"""Tests for the Osmocom HLR methods at core.subscriber._osmocom

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.

Run this test from the project root:
    $ nosetests core.tests.osmocom_subscriber_tests
"""

import mock
from random import randrange
import unittest

from core.subscriber import _osmocom
from core.subscriber.base import SubscriberNotFound


class SubscriberTest(unittest.TestCase):
    """ Testing the subscriber API implementation

    The _osmocom modules translates the generic subscriber API operations
    into calls to the Osmocom HLR. For testing purposes we can mock the
    HLR interface (the 'send' query operation).
    """

    TEST_IMSI = 'IMSI234569876543210'
    TEST_MSISDN = '12155551212'

    @classmethod
    @mock.patch('core.subscriber._osmocom.Subscribers', autospec=True)
    def setUpClass(cls, mock_osmocom_subs):
        # create a Mock for instance of HLR connection
        cls._mock_hlr = mock.Mock()
        mock_osmocom_subs.return_value = cls._mock_hlr
        cls._hlr = _osmocom.OsmocomSubscriber()
        # verify that mock_hlr attached (sanity check)
        assert cls._hlr.subscribers == cls._mock_hlr
        # _osmocom module uses a context manager for all HLR operations
        cls._mock_ctx = mock.Mock()
        cls._mock_hlr.__enter__ = mock.Mock(return_value=cls._mock_ctx)
        cls._mock_hlr.__exit__ = mock.Mock(return_value=False)

    def test_add_delete_subscriber(self):
        """ Add and delete a known IMSI. """
        imsi = 'IMSI%015d' % (randrange(1e14, 9e14), )
        msisdn = str(randrange(1.1e9, 1.99e9))

        # First call to show should raise exception since IMSI not present,
        # but second should return a dict corresponding to the subscriber.
        self._hlr.imsi_added = False

        def show(_type, _imsi):
            if not self._hlr.imsi_added:
                raise ValueError()
            return {'imsi': imsi[4:],
                    'extension': msisdn,
                    'authorized': '1'}
        self._mock_ctx.show = mock.Mock(side_effect=show)

        # Calling create should mark the IMSI as added.
        def create(_imsi):
            self._hlr.imsi_added = True
        self._mock_ctx.create = mock.Mock(side_effect=create)

        # Add the subscriber
        self._hlr.add_subscriber_to_hlr(imsi, msisdn, None, None)

        # Check that we can lookup by IMSI and number.
        self.assertEqual(self._hlr.get_caller_id(imsi), msisdn)
        self.assertEqual(self._hlr.get_imsi_from_number(msisdn), imsi)

        # Check that we can check if an IMSI is authorized.
        with mock.patch.object(self._hlr, 'get_subscriber_states') as _get:
            _get.return_value = [{}]  # need to return a non-empty list
            self.assertTrue(self._hlr.is_authed(imsi))

        # Now delete that IMSI.
        self._hlr.delete_subscriber_from_hlr(imsi)

        # Check that methods were called as expected
        self._mock_ctx.create.assert_called_once_with(imsi)
        self._mock_ctx.set_extension.assert_called_once_with(imsi, msisdn)
        self._mock_ctx.set_authorized.assert_called_once_with(imsi, True)
        self._mock_ctx.delete.assert_called_once_with(imsi)

    def test_delete_unknown(self):
        """ Deleting an unknown IMSI raises an exception. """
        with self.assertRaises(SubscriberNotFound,
                               msg=self.TEST_IMSI):
            # Osmocom HLR raises ValueError for non-existent IMSI
            self._mock_ctx.delete = mock.Mock(side_effect=ValueError())
            self._hlr.delete_subscriber_from_hlr(self.TEST_IMSI)
        # check that delete was called as expected
        self._mock_ctx.delete.assert_called_once_with(self.TEST_IMSI)

    def test_get_unknown_imsi(self):
        """ Looking up an unknown IMSI raises an exception. """
        with self.assertRaises(SubscriberNotFound,
                               msg=self.TEST_IMSI):
            # Osmocom HLR raises ValueError for non-existent IMSI
            self._mock_ctx.show = mock.Mock(side_effect=ValueError())
            self._hlr.get_caller_id(self.TEST_IMSI)
        # check that show was called as expected
        self._mock_ctx.show.assert_called_once_with('imsi', self.TEST_IMSI)

    def test_get_unknown_number(self):
        """ Looking up an unknown MSISDN raises an exception. """
        with self.assertRaises(SubscriberNotFound,
                               msg=('MSISDN %s' % (self.TEST_MSISDN, ))):
            # Osmocom HLR raises ValueError for non-existent IMSI
            self._mock_ctx.show = mock.Mock(side_effect=ValueError())
            self._hlr.get_imsi_from_number(self.TEST_MSISDN)
        # check that show was called as expected
        self._mock_ctx.show.assert_called_once_with('extension',
                                                    self.TEST_MSISDN)

    def test_check_auth_unknown_imsi(self):
        """ Checking authentication of an unknown IMSI returns False. """
        with mock.patch.object(self._hlr, 'get_subscriber_states') as _get:
            _get.return_value = [{}]  # need to return a non-empty list
            # Osmocom HLR raises ValueError for non-existent IMSI
            self._mock_ctx.show = mock.Mock(side_effect=ValueError())
            self.assertFalse(self._hlr.is_authed(self.TEST_IMSI))
            # check that show was called as expected
            self._mock_ctx.show.assert_called_once_with('imsi', self.TEST_IMSI)
