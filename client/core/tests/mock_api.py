"""This mocks functionality of the Endaga API for testing.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import json
import random

import web

from ccm.common import logger
from core.config_database import ConfigDB
import snowflake


URLS_NOMINAL = ("/bts/register/", "MockBTSRegistration",
        "/fetch/(.*)/", "MockNumberAllocation",
        "/register/", "MockRegistration")
APP_NOMINAL = web.application(URLS_NOMINAL, globals())
CONF = ConfigDB()


class MockBTSRegistration:
    """This class mocks the /bts/register endpoint, empty for now."""

    def GET(self):
        logger.info('GET mock bts register')
        return web.forbidden()


class MockNumberAllocation:
    """This class mocks out the /fetch/<uuid> endpoint."""

    def GET(self, uuid):
        logger.info('GET mock number allocation with env: %s' % str(web.ctx.env))
        auth_token = web.ctx.env['HTTP_AUTHORIZATION']
        assert uuid == snowflake.snowflake()
        assert auth_token == "Token %s" % CONF['endaga_token']
        return '1%010d' % random.randint(1000000000, 9999999999)


class MockRegistration:
    """This class mocks the /register/?imsi=<imsi>&bts_uuid=<bts_uuid> endpoint"""

    def POST(self):
        data = web.input()
        # The auth token should be here.
        logger.info('GET mock subscriber provision')
        auth_token = web.ctx.env['HTTP_AUTHORIZATION']
        assert data.bts_uuid == snowflake.snowflake()
        assert len(data.imsi) == 19
        assert auth_token == "Token %s" % CONF['endaga_token']
        return json.dumps({ 'number': '1%010d' % random.randint(1000000000, 9999999999) })


URLS_BAD_NUMBER_ALLOCATION = ("/fetch/(.*)/", "MockFailedNumberAllocation")
APP_BAD_NUMBER_ALLOCATION = web.application(
    URLS_BAD_NUMBER_ALLOCATION, globals())


class MockFailedNumberAllocation:
    """This mocks a failed attempt to reach the /fetch/<uuid> endpoint."""

    def GET(self, uuid):
        return web.forbidden()


URLS_BAD_REGISTRATION = ("/register/(.*)/(.*)/", "MockFailedRegistration")
APP_BAD_REGISTRATION = web.application(URLS_BAD_REGISTRATION, globals())


class MockFailedRegistration:
    """Mocks a failure to reach /register/<uuid>/<number>/?imsi=<imsi> ."""

    def GET(self, uuid, number):
        return web.forbidden()


if __name__ == "__main__":
    APP_NOMINAL.run()
