
"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import abc
from .store.util import SIDUtils

from .store.protos.subscriber_pb2 import GSMSubscription, SubscriberID
from .crypto.gsm import UnsafePreComputedA3A8
from .crypto.utils import CryptoError


class GSMProcessor(metaclass=abc.ABCMeta):
    """
    Interface for the GSM protocols to interact with other parts
    of subscriberdb.
    """

    @abc.abstractmethod
    def get_gsm_auth_vector(self, imsi):
        """
        Returns the gsm auth tuple for the subsciber by querying the store
        for the secret key.

        Args:
            imsi: the subscriber identifier
        Returns:
            the auth tuple (rand, sres, key) returned by the crypto object
        Raises:
            SubscriberNotFoundError if the subscriber is not present
            CryptoError if the auth tuple couldn't be generated
        """
        raise NotImplementedError()

class Processor(GSMProcessor):
    """
    Core class which glues together all protocols, crypto algorithms and
    subscriber stores.
    """

    def __init__(self, store):
        """
        Init the Processor with all the components.

        We use the UnsafePreComputedA3A8 crypto by default for
        GSM authentication. This requires the auth-tuple to be stored directly
        in the store as the key for the subscriber.
        """
        self._store = store

    def get_gsm_auth_vector(self, imsi):
        """
        Returns the gsm auth tuple for the subsciber by querying the store
        for the crypto algo and secret keys.
        """
        sid = SIDUtils.to_str(SubscriberID(id=imsi, type=SubscriberID.IMSI))
        subs = self._store.get_subscriber_data(sid)

        if subs.gsm.state != GSMSubscription.ACTIVE:
            raise CryptoError("GSM service not active for %s" % sid)

        # The only GSM crypto algo we support now
        if subs.gsm.auth_algo != GSMSubscription.PRECOMPUTED_AUTH_TUPLES:
            raise CryptoError("Unknown crypto (%s) for %s" %
                              (subs.gsm.auth_algo, sid))
        gsm_crypto = UnsafePreComputedA3A8()

        if len(subs.gsm.auth_tuples) == 0:
            raise CryptoError("Auth key not present for %s" % sid)

        return gsm_crypto.generate_auth_tuple(subs.gsm.auth_tuples[0])
