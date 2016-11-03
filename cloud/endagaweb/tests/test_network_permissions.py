"""Tests for multiple user accounts and permissions roles on a network,

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import urllib
from unittest import TestCase

from guardian.shortcuts import *
from endagaweb import models


class SingleUserNetwork(TestCase):

    @classmethod
    def tearDownClass(cls):
        """Clean up created objects."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.network.delete()

    @classmethod
    def setUpClass(cls):
        """Setup a User and associated Network."""
        cls.user = models.User(username="j", email="j@k.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.network = cls.user_profile.network

    def test_network_default_auth_group(self):
        """There is an auth group for the network and it has two
        users: the network auth user."""
        self.assertEqual(2, self.network.auth_group.user_set.count())
        self.assertTrue(self.network.auth_group.user_set.
            filter(id=self.user.id).exists())
        self.assertTrue(self.network.auth_group.user_set.
            filter(id=self.network.auth_user.id).exists())

    def test_network_default_user_permissions(self):
        """By default all users added to the network auth group
        have view_network permission."""
        self.assertEqual(['view_network'], get_perms(self.user, self.network))
        self.assertEqual(['view_network'], get_perms(self.network.auth_user, self.network))


class MultiUserNetwork(TestCase):

    @classmethod
    def tearDownClass(cls):
        """Clean up created objects."""
        cls.user.delete()
        cls.user_profile.delete()
        cls.network.delete()

    @classmethod
    def setUpClass(cls):
        """Setup a User and associated Network."""
        cls.user = models.User(username="j", email="j@k.com")
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.network = cls.user_profile.network

    def setUp(self):
        """Set up the secondary user"""
        self.user2 = models.User(username="k", email="l@m.com")
        self.user2.save()
        self.user_profile2 = models.UserProfile.objects.get(user=self.user2)
        self.network2 = self.user_profile2.network

    def tearDown(self):
        """Clean up the secondary user after each test."""
        self.user2.delete()
        self.user_profile2.delete()
        self.network2.delete()

    def test_secondary_default_user_no_access(self):
        """By default the second user cannot access the first network."""
        self.assertFalse(self.user2.has_perm('view_network', self.network))

    def test_superuser_can_see_all(self):
        """Superuser can see all networks"""
        self.user2.is_superuser = True
        self.user2.save()
        self.assertLess(1,
            get_objects_for_user(self.user2, 'view_network', klass=models.Network).count())

    def test_add_new_user_permissions(self):
        """When a new user is added to the network auth group, they assume the group
        permissions as well."""
        self.network.auth_group.user_set.add(self.user2)
        self.assertEqual(3, self.network.auth_group.user_set.count())
        self.assertTrue(self.user2.has_perm('view_network', self.network))
        self.assertItemsEqual([self.network, self.network2],
            get_objects_for_user(self.user2, 'view_network', klass=models.Network))

        # We can also remove them
        self.network.auth_group.user_set.remove(self.user2)
        self.assertEqual(2, self.network.auth_group.user_set.count())
        self.assertFalse(self.user2.has_perm('view_network', self.network))
        self.assertItemsEqual([self.network2],
            get_objects_for_user(self.user2, 'view_network', klass=models.Network))
