"""The client's primary server.

Handles commands sent by the cloud, incoming SMS, delivery receipts, subscriber
provisioning and parsing CDRs.

Receives CDRs from Freeswitch mod_xml_cdr and updates subscriber registry
accordingly.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import web
import traceback

from ccm.common import logger


urls = (
    "/endaga_sms", "core.federer_handlers.sms.endaga_sms",
    "/out_endaga_sms", "core.federer_handlers.sms.OutgoingSMSHandler",
    "/endaga_registration",
        "core.federer_handlers.registration.endaga_registration",
    "/config/(.*)", "core.federer_handlers.config.config",
    "/cdr", "core.federer_handlers.cdr.cdr",
    "/smscdr", "core.federer_handlers.sms_cdr.smscdr"
)

def handle_with_logging(self):
    def process(processors):
        try:
            if processors:
                p, processors = processors[0], processors[1:]
                return p(lambda: process(processors))
            else:
                return self.handle()
        except web.HTTPError as e:
            logger.error("Web error: %s" % e)
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            logger.critical("Unhandled exception raised",
                    traceback=traceback.format_exc())
            raise self.internalerror()

    # processors must be applied in the resvere order. (??)
    return process(self.processors)

# monkeypatch to allow error capturing
web.application.handle_with_processors = handle_with_logging

app = web.application(urls, locals())


if __name__ == "__main__":
    app.run()
