"""
Tests for the lock service.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import time
import pytz
from datetime import datetime

from django.db import transaction
from django.test import TestCase

from endagaweb import models
from endagaweb.util import dbutils

"""
Base class that provides common mocks across lock related test classes
"""


class LockTestCaseBase(TestCase):

    @classmethod
    def setUpClass(cls):
        def mock_lookup(_):
            u = datetime.utcnow()
            return u.replace(tzinfo=pytz.utc)
        cls.get_db_time = dbutils.get_db_time
        dbutils.get_db_time = mock_lookup

    @classmethod
    def tearDownClass(cls):
        dbutils.get_db_time = cls.get_db_time


class LockTest(LockTestCaseBase):

    def setUp(self):
        self.key = 'test lock'
        self.lock = models.Lock(key=self.key, ttl=1)
        self.lock.save()

    def tearDown(self):
        self.lock.delete()

    def test_take_lock(self):
        """ We can take the lock. """
        self.assertTrue(self.lock.lock('test1'))
        self.assertTrue(self.lock.lock('test1'))
        self.lock = models.Lock.objects.get(id=self.lock.id)
        self.assertFalse(self.lock.lock('test2'))

    def test_expiring_lock(self):
        """
        Take the lock, make it expire in the future, try to take lock with
        another value.
        """
        self.lock.lock("test1")
        self.lock = models.Lock.objects.get(id=self.lock.id)
        self.assertFalse(self.lock.lock('test2'))
        time.sleep(1.4) # wait for lock to expire
        self.lock = models.Lock.objects.get(id=self.lock.id)
        self.assertTrue(self.lock.lock('test2'))

    def test_update_lock(self):
        self.assertTrue(self.lock.lock('test1'))
        time.sleep(0.8) # lock hasn't expired
        self.lock = models.Lock.objects.get(id=self.lock.id)
        self.assertTrue(self.lock.lock('test1'))
        time.sleep(0.4) # lock has now expired
        self.lock = models.Lock.objects.get(id=self.lock.id)
        self.assertFalse(self.lock.lock('test2'))

    def test_unlock(self):
        self.lock.lock('test1')
        self.lock.unlock('test1')
        self.assertTrue(self.lock.lock('test2'))


class LockStaticWrapperTest(LockTestCaseBase):

    def tearDown(self):
        models.Lock.objects.all().delete()

    def test_take_lock(self):
        self.assertTrue(models.Lock.grab("cb", "i-1234", ttl=1))
        self.assertTrue(models.Lock.grab("cb", "i-1234"))
        self.assertFalse(models.Lock.grab("cb", "i-7890"))

    def test_expiration(self):
        self.assertTrue(models.Lock.grab("cb", "i-1234", ttl=1))
        time.sleep(0.5)
        self.assertFalse(models.Lock.grab("cb", "i-7890"))
        #some timing issues cause it to fail at times just after (but still near) ttl
        #so let's test a bit farther off that
        time.sleep(0.7)
        self.assertTrue(models.Lock.grab("cb", "i-7890"))

    def test_release(self):
        self.assertTrue(models.Lock.grab("cb", "i-1234"))
        self.assertTrue(models.Lock.release("cb", "i-1234"))
        self.assertTrue(models.Lock.grab("cb", "i-7890"))

    def test_wait(self):
        self.assertTrue(models.Lock.wait("cb", "i-1234", ttl=1))
        self.assertTrue(models.Lock.wait("cb", "i-1234"))
        self.assertTrue(models.Lock.wait("cb", "i-7890"))
