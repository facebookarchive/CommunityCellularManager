"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import types
import copy
from .protocol import DeltaProtocolCtx, DeltaProtocol


class DeltaProtocolOptimizer(object):
    """
    DeltaProtocolOptimizer provides client (process) & server (prepare) side
    optimization wrappers to be used to reduce size of data sent repeatedly
    from server to client
    If the majority of the server provided data (in this case a python
    dictionary) is the same, it's more efficient to send only the changed parts
    (delta) with extra information allowing client to verify the received delta
    & the recovered data compatibility & correctness, such as MD5s of old and
    new (old + delta) dictionary, etc.

    Attributes:
        ctx (DeltaProtocolCtx): a persistent context used by client or server
                                to preserve the state of optimized data
                                between transactions.
        last_used_ts (int): the time, the instance was last used by a sever
                            (prepare). For use by a garbage collector to limit
                            the size of consumed memory

    """
    SECTIONS_CTX_KEY = 'sections'

    def __init__(self, ctx=None):
        if ctx is None:
            ctx = DeltaProtocolCtx()
        self.ctx = ctx
        self.last_used_ts = time.time()

    def process(self, dict_or_delta):
        """
        CLIENT side process method, for use by clients to apply delta
        transparently
        :param dict_or_delta: dictionary representing one of
            the following three elements:
              1) Regular dictionary without any delta specific information,
                 such dictionary causes noop and just returned back to caller
              2) Regular dictionary with one special DeltaProtocol.CTX_KEY
                 element. In this case CTX_KEY is used to initialize ctx,
                 CTX_KEY is removed from the dictionary before the dictionary
                 is returned
              3) Delta dictionary. In this case delta is applied to existing
                 ctx.data, application is checksummed & verified and the
                  resulting dictionary is returned to the caller

        :return: either original dictionary, original dictionary with
                 DeltaProtocol.CTX_KEY key removed or ctx.data after applied
                 delta
        Throws ValueError if delta is passed, but ctx is not initialized or
        doesn't match the delta
        """
        if DeltaProtocol.is_delta(dict_or_delta):
            if self.ctx.data is None:
                self.ctx.reset()
                # We have no choice, but throw here - we cannot
                # return un-applied, invalid delta to a caller not
                # expecting it
                raise ValueError("Unexpected Delta Without Prior State")

            try:
                return self.ctx.apply_delta(dict_or_delta)
            except:  # noqa: B001 T25377293 Grandfathered in
                # apply_delta will throw if there is sig mismatch,
                # we need to clear state
                self.ctx.reset()
                raise
        else:
            # Clent always initiates delta protocol, so we set self.ctx
            # even if server didn't send any CTX or delta
            cap_ctx = DeltaProtocol.find_delta_capable_ctx(dict_or_delta)
            try:
                if cap_ctx:
                    dict_or_delta.pop(DeltaProtocol.CTX_KEY)
                    sig_algo = cap_ctx[DeltaProtocol.SIG_ALG_KEY]
                else:
                    sig_algo = DeltaProtocol.DEFAULT_DIGEST_ALGO

                dict_or_delta = copy.deepcopy(dict_or_delta)
                DeltaProtocol.sort_lists(dict_or_delta)
                curr_sig = DeltaProtocol.make_digest(dict_or_delta, sig_algo)
                self.ctx.set(dict_or_delta, curr_sig, sig_algo)

            except Exception as e:
                # clear state if we cannot work with provided sig/data
                self.ctx.reset()
                print('Unhandled delta.process exception: %s' % str(e))

            return dict_or_delta

    def prepare(self, client_ctx, data):
        """
        Prepares data to be sent to delta capable client
        If passed is not a dictionary, it'll be ignored, optimization won't
        be performed and CTX won't be updated, but the function should not fail
        and will return original data

        :param client_ctx: CTX received from the client for this data
        :param data: data to be optimized (if possible)
        :return: either original data (may be sorted) or delta to be sent
        """
        if not isinstance(data, dict):
            return data

        try:
            if client_ctx and client_ctx.sig and client_ctx.sig_algo:
                if (self.ctx.data and
                        self.ctx.sig_algo == client_ctx.sig_algo and
                        self.ctx.sig == client_ctx.sig):

                    delta = DeltaProtocol.make_delta(
                        data,
                        self.ctx.data,
                        client_ctx.sig,
                        client_ctx.sig_algo
                    )
                    new_sig = delta[DeltaProtocol.SIG_KEY].get(
                        DeltaProtocol.SIG_NEW_KEY
                    )
                    if new_sig:
                        self.ctx.sig = new_sig
                        self.ctx.data = copy.deepcopy(data)
                    return delta

                else:
                    # client sent CTX, but server doesn't have a state for it
                    # or the server state doesn't match.
                    # in this case see if the the new config sig is identical
                    # to the client's and send empty delta if it is
                    DeltaProtocol.sort_lists(data)
                    new_sig = DeltaProtocol.make_digest(data,
                                                        client_ctx.sig_algo)
                    if new_sig == client_ctx.sig:
                        self.ctx.set(copy.deepcopy(data),
                                     new_sig,
                                     client_ctx.sig_algo)
                        return DeltaProtocol.make_empty_delta(
                            new_sig,
                            client_ctx.sig_algo
                        )

                    # if client_ctx is not initialized or invalid/mismatched
                    # append a new ctx to data and update self.ctx to reflect it
                    if DeltaProtocol.CTX_KEY not in data:
                        self.ctx.set(copy.deepcopy(data),
                                     new_sig,
                                     client_ctx.sig_algo)
                        data[DeltaProtocol.CTX_KEY] = self.ctx.to_proto_dict()

            self.last_used_ts = time.time()  # update TS for server cache

        except Exception as e:  # on any error just return original data
            self.ctx.reset()
            print('Unhandled delta.prepare exception: %s' % str(e))

        return data

    def match_sig_ctx(self, delta):
        if delta and DeltaProtocol.SIG_KEY in delta:
            sig = delta.get(DeltaProtocol.SIG_KEY)
            return (isinstance(sig, dict) and
                    sig.get(DeltaProtocol.SIG_ALG_KEY) == self.ctx.sig_algo and
                    sig.get(DeltaProtocol.SIG_OLD_KEY) == self.ctx.sig)


class DeltaProtocolOptimizerFactory(object):
    """
    DeltaProtocolOptimizerFactory - provides functionality of
    DeltaProtocolOptimizer cache, including creation, lookup & garbage
    collection of DeltaProtocolOptimizer objects
    """
    def __init__(self, max_size=256, max_ttl_sec=43200, gc_interval_sec=300):
        self._optimizers = {}
        self._max_size = max_size
        self._ttl = max_ttl_sec
        self._gc_interval = gc_interval_sec
        self._last_gc_time = time.time()

    def _gc(self):
        tm = time.time()
        if self._last_gc_time + self._gc_interval >= tm:
            return
        self._last_gc_time = tm
        stale_time = tm - self._ttl
        # first - delete all stale optimizers
        for k, v in self._optimizers.iteritems():  # noqa: B301 T25377293 Grandfathered in
            if (not isinstance(v, DeltaProtocolOptimizer) or
                    v.last_used_ts < stale_time):
                self._optimizers.pop(k)

        # if we a still above max size threshold - remove oldest, this is a
        # crapshoot, we may be just trashing removing 'oldest' which are about
        # to be utilized, we'll have to tune it later...
        if len(self._optimizers) > self._max_size:
            oldest_sort = sorted(
                self._optimizers.iteritems(),  # noqa: B301 T25377293 Grandfathered in
                key=lambda k, v: v.last_used_ts
            )
            for k, v in oldest_sort[:len(self._optimizers) - self._max_size]:  # noqa: B007 T25377293 Grandfathered in
                self._optimizers.pop(k)

    def clear(self):  # delete all optimizers
        self._optimizers.clear()

    def get(self, id):
        optimizer = self._optimizers.get(id)
        if optimizer is None:
            if len(self._optimizers) >= self._max_size:
                self._gc()
            optimizer = DeltaProtocolOptimizer()
            self._optimizers[id] = optimizer
        return optimizer


def DeltaCapable(ctx=None, skip_empty=False):
    """
    Client side class method decorator, to be used with response processing
    member functionexpecting self first parameter and config/param dictionary as
    the second, parameter

    :param ctx: An optional context object to be used for the delta state
                persistence if none is provided, decorator will allocate & use
                one internally
    :param skip_empty: a flag to instruct the decorator to skip the decorated
                       function call completely on empty deltas
    """

    optimizer = DeltaProtocolOptimizer(ctx)
    skip_if_empty_delta = skip_empty

    def delta_capable_impl(f):
        def check_and_apply_delta(*args, **kwargs):
            if not (args and
                    len(args) > 1 and
                    isinstance(args[0], object) and
                    isinstance(args[1], dict)):
                return f(*args, **kwargs)

            possible_delta = args[1]
            if DeltaProtocol.is_delta(possible_delta):
                if (skip_if_empty_delta and
                        possible_delta.get(DeltaProtocol.DIFF_KEY) == {} and
                        optimizer.match_sig_ctx(possible_delta)):
                    return None

            new_dict = optimizer.process(possible_delta)
            args = list(args)
            args[1] = new_dict
            return f(*args, **kwargs)

        return check_and_apply_delta
    return delta_capable_impl


def DeltaCapableFunction(ctx=None, skip_empty=False):
    """
    Client side decorator, to be used with response processing function
    expecting the config/param dictionary as the first parameter

    :param ctx: An optional context object to be used for the delta state
                persistence if none is provided, decorator will allocate & use
                one internally
    :param skip_empty: a flag to instruct the decorator to skip the decorated
                       function call completely on empty deltas
    """
    optimizer = DeltaProtocolOptimizer(ctx)
    skip_if_empty_delta = skip_empty

    def delta_capable_impl(f):
        def check_and_apply_delta(*args, **kwargs):
            if not (args and len(args) and isinstance(args[0], dict)):
                return f(*args, **kwargs)

            possible_delta = args[0]
            if DeltaProtocol.is_delta(possible_delta):
                if (skip_if_empty_delta and
                        possible_delta.get(DeltaProtocol.DIFF_KEY) == {} and
                        optimizer.match_sig_ctx(possible_delta)):
                    return None

            new_dict = optimizer.process(possible_delta)
            args = list(args)
            args[0] = new_dict
            return f(*args, **kwargs)

        return check_and_apply_delta
    return delta_capable_impl
