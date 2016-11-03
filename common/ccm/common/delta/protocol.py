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

import copy
import hashlib
import json

import six

from . import dictdiff


class DeltaProtocol(object):
    """
    DeltaProtocol provides core delta optimization functionality and helpers,
    the class is 'static' and used for encapsulation & namespacing
    """
    DEFAULT_DIGEST_ALGO = 'md5'  # default hash algorithm used for signatures
    DIFF_KEY = '+/-'  # key used to denote the delta
    SIG_KEY = 'sig'  # key of the delta signatures block
    SIG_ALG_KEY = 'alg'  # key of the signatures' algorithm ('md5')
    SIG_NEW_KEY = 'new'
    # SIG_NEW_KEY - verification hash of dictionary after apply delta
    # used by client to make sure there is no data coruption or algorithm
    # mismatch: delta(old) => new

    SIG_OLD_KEY = 'old'
    # SIG_OLD_KEY - verification hash of dictionary used to create delta which
    # transfers the old dictionary to the new dictionary

    CTX_KEY = '+/-ctx'  # CTX key 4 client to notify server of the current CTX
    CTX_HASH_KEY = 'sig'  # Client's current data hash key from client's CTX

    @staticmethod
    def make_delta(new, old, old_hash=None, hash_algo=DEFAULT_DIGEST_ALGO):
        """
        creates delta dictionary in the form: {
            '+/-': { # see dictdiff.py
                '+': ..., '-': ...
            },
            'sig': {
                'alg' : 'md5',
                'old' : 'xYz....',
                'new' : 'XyZ....'
            }
        }
        :param new: new param dictionary
        :param old: old param dictionary
        :param hash_algo: digest algorithm to use, default = 'md5'
        :param old_hash: the hash of old dictionary (if given)
        :return: delta (see above) if new differs from old,
             {'+/-':{}, 'sig': {'alg' : 'md5', 'old' : 'XyZ..'}} if old == new
        """
        DeltaProtocol.sort_lists(new)  # make sure, all lists are ordered for
        DeltaProtocol.sort_lists(old)  # comparison & md5

        diff = dictdiff.diff(new, old)
        if diff is None:
            raise TypeError("Invalid Parameters")
        if old_hash is None:
            old_hash = DeltaProtocol.make_digest(old, hash_algo)

        delta = {
            DeltaProtocol.DIFF_KEY: diff,
            DeltaProtocol.SIG_KEY: {
                DeltaProtocol.SIG_ALG_KEY: hash_algo,
                DeltaProtocol.SIG_OLD_KEY: old_hash
            }
        }

        if diff:
            delta[DeltaProtocol.SIG_KEY][DeltaProtocol.SIG_NEW_KEY] = \
                DeltaProtocol.make_digest(new, hash_algo)

        return delta

    @staticmethod
    def make_empty_delta(data_hash, hash_algo=DEFAULT_DIGEST_ALGO):
        return {
            DeltaProtocol.DIFF_KEY: {},
            DeltaProtocol.SIG_KEY: {
                DeltaProtocol.SIG_ALG_KEY: hash_algo,
                DeltaProtocol.SIG_OLD_KEY: data_hash
            }
        }

    @staticmethod
    def apply_delta(delta, current, current_hash=None, curr_hash_type = None):
        """
        applies given delta to current dictionary and returns
        the updated dictionary, new hash & hash type
        :param delta: a delta between current and new data
        :param current: old data
        :param current_hash: hash of old data
        :param curr_hash_type: hash algorithm (currently only MD5)
        :return: tuple consisting of:
                 1. updated dictionary,
                 2. new dictionary hash and
                 3. new dictionary hash type
        """
        if not isinstance(delta, dict):
            raise ValueError("Illegal Delta Object")

        diff = delta.get(DeltaProtocol.DIFF_KEY)
        sig = delta.get(DeltaProtocol.SIG_KEY)
        if diff is None or sig is None:
            raise ValueError("Invalid Delta Format")

        if not isinstance(diff, dict):
            raise ValueError("Invalid Delta Diff Object")

        if not isinstance(sig, dict):
            raise ValueError("Illegal Delta Signature")

        hash_algo = sig.get(DeltaProtocol.SIG_ALG_KEY)
        old_hash = sig.get(DeltaProtocol.SIG_OLD_KEY)
        if hash_algo is None or old_hash is None:
            raise ValueError("Invalid Delta Signature Format")

        if diff and DeltaProtocol.SIG_NEW_KEY not in sig:
            raise ValueError("Missing New Signature Hash ")

        if (current_hash is None
                or curr_hash_type is None
                or curr_hash_type != hash_algo):
            current_hash = DeltaProtocol.make_digest(current, hash_algo)

        if old_hash != current_hash:
            raise ValueError("Delta Old Hash Mismatch")

        if diff:
            newval = dictdiff.apply_delta(current, diff)
            if newval is None:
                raise TypeError("Invalid Delta Diff Structure")
            DeltaProtocol.sort_lists(newval)
            new_hash = DeltaProtocol.make_digest(newval, hash_algo)
            if new_hash != sig[DeltaProtocol.SIG_NEW_KEY]:
                raise ValueError("Delta New Hash Mismatch")
            return newval, new_hash, hash_algo
        else:
            return current, current_hash, hash_algo

    @staticmethod
    def make_delta_ctx_obj(curr_dict, hash_algo=DEFAULT_DIGEST_ALGO):
        """
        creates & returns delta request CTX object with following members:
            ctx.data  (reference to the passed curr_dict)
            ctx.sig ('XyZ...')
            ctx.sig_algo (passed hash_algo or default DEFAULT_DIGEST_ALGO if none)

        :param curr_dict: param dictionary to to use as the context source
        :param hash_algo: digest algorithm to use, default = 'md5'
        :return: delta ctx object (see above)
        """
        if not isinstance(curr_dict, dict):
            raise TypeError("Invalid Parameter, must be a dict")

        DeltaProtocol.sort_lists(curr_dict)
        hash = DeltaProtocol.make_digest(curr_dict, hash_algo)
        return DeltaProtocolCtx(curr_dict, hash, hash_algo)

    @staticmethod
    def make_delta_ctx(curr_dict, hash_algo=DEFAULT_DIGEST_ALGO):
        """
        creates delta request CTX in the form: {
            'alg' : 'md5',
            'sig' : 'xYz....'
        }
        :param curr_dict: param dictionary to to use as the context source
        :param hash_algo: digest algorithm to use, default = 'md5'
        :param old_hash: the hash of old dictionary (if given)
        :return: delta ctx (see above)
        """
        ctx = DeltaProtocol.make_delta_ctx_obj(curr_dict, hash_algo)
        return {
            DeltaProtocol.SIG_ALG_KEY: ctx.sig_algo,
            DeltaProtocol.CTX_HASH_KEY: ctx.sig
        }

    @staticmethod
    def append_delta_ctx(curr_dict, hash_algo=DEFAULT_DIGEST_ALGO):
        if isinstance(curr_dict, dict) and DeltaProtocol.CTX_KEY not in curr_dict:
            curr_dict[DeltaProtocol.CTX_KEY] = DeltaProtocol.make_delta_ctx(curr_dict)
            return True
        return False

    @classmethod
    def find_delta_capable_ctx(cls, dict_with_ctx):
        """
        Delta Capable Context is passed alone with an initial dictionary
        to indicate that the server is capable of delta algorithm to
        be used for following dictionary updates. Client may either
        ignore the passed ctx and not take advantage of delta
        optimization or save it and pass CTX back to the server in
        consecutive requests

        :param dict_with_ctx: a dictionary which MAY include a special
        delta CTX element in the form:
            '+/-ctx': {'alg' : 'md5', 'sig' : 'xYz....'}

        :return: CTX value ({'alg' : 'md5', 'sig' : 'xYz....'}) if found,
        None otherwise
        """
        if isinstance(dict_with_ctx, dict):
            ctx_v = dict_with_ctx.get(cls.CTX_KEY)
            if (ctx_v and isinstance(ctx_v, dict) and
                isinstance(ctx_v.get(cls.SIG_ALG_KEY), six.string_types) and
                isinstance(ctx_v.get(cls.CTX_HASH_KEY), six.string_types) and
                len(ctx_v) == 2):  # noqa: E129
                return ctx_v

        return None

    @staticmethod
    def make_digest(obj, hash_algo=DEFAULT_DIGEST_ALGO):
        m = hashlib.new(hash_algo)
        m.update(
            json.dumps(
                obj, ensure_ascii=False, sort_keys=True
            ).encode('utf-8')
        )
        return m.hexdigest()

    @staticmethod
    def is_delta(possible_delta):
        if (isinstance(possible_delta, dict) and
                DeltaProtocol.DIFF_KEY in possible_delta and
                DeltaProtocol.SIG_KEY in possible_delta and
                len(possible_delta) == 2 and
                isinstance(possible_delta[DeltaProtocol.DIFF_KEY], dict)):

            sig = possible_delta[DeltaProtocol.SIG_KEY]
            return (isinstance(sig, dict) and
                    DeltaProtocol.SIG_ALG_KEY in sig and
                    DeltaProtocol.SIG_OLD_KEY in sig and
                    len(sig) <= 3)
        return False

    @staticmethod
    def sort_lists(dct):
        if isinstance(dct, dict):
            for k, v in six.iteritems(dct):
                if isinstance(v, list):
                    if v == []:
                        continue
                    # check for lists of dicts, Python 3 won't sort them
                    if isinstance(v[0], dict):
                        list_of_dicts = []
                        for i in v:
                            # we don't really want to deal with mixed lists
                            if not isinstance(i, dict):
                                raise TypeError("expected dict")
                            # convert each dict to a (k, v) list
                            i_list = list(i.items())
                            # sort the (k, v) list
                            i_list.sort()
                            # list of dicts is a list of the (k, v) lists
                            list_of_dicts += [i_list]
                        # now sort that list of lists
                        list_of_dicts.sort()
                        # reconstitute into a sorted list of dicts
                        dct[k] = [dict(items) for items in list_of_dicts]
                    else:
                        # convert list elements to strings to compare them
                        v.sort(key=str)
                elif isinstance(v, dict):
                    DeltaProtocol.sort_lists(v)


class DeltaProtocolCtx(object):
    """
    Class used for persisting client's or server's delta optimization context
    between transactions. The context consists of last seen data dictionary,
    last data signature (for faster verifications) and signature algorithm
    (currently we only use MD5, but may choose to support something more
    expensive in the future)
    """
    def __init__(self,
                 data=None,
                 sig=None,
                 sig_algo=DeltaProtocol.DEFAULT_DIGEST_ALGO):
        """
        Constructor
        Args:
            data: the data being optimized
                  Note: an empty dict {} is a valid initialized value
                  representing empty data set while None represents
                  unset/unused data value
            sig: signature of the data
            sig_algo: the signature algorithm used
        """
        self.set(data, sig, sig_algo)

    def is_valid(self):
        return self.sig is not None and (self.data is not None or
                                         self.sig_algo is not None)

    def __nonzero__(self):
        return self.is_valid()

    def __bool__(self):
        # aaargh, Python 3 changed the method name
        return self.__nonzero__()

    def __repr__(self):
        # good for debugging
        return ("{ sig: %s, sig_algo: %s: " % (self.sig, self.sig_algo) +
                ("data.keys: %s" % self.data.keys() if self.data else
                 "data: None") +
                " }")

    def reset(self):
        self.data = None
        self.sig = None
        self.sig_algo = None

    def set(self, data, sig, sig_algo=DeltaProtocol.DEFAULT_DIGEST_ALGO):
        self.data = data
        self.sig = sig
        self.sig_algo = sig_algo

    def to_proto_dict(self):
        """
        A convenience function, creates a dict in the form:
        {'sig': self.sig, 'alg': self.sig_algo} to be used in delta protocol
        implementation

        Returns: {'sig': self.sig, 'alg': self.sig_algo}

        """
        return {
            DeltaProtocol.CTX_HASH_KEY: self.sig,
            DeltaProtocol.SIG_ALG_KEY: self.sig_algo
        }

    def apply_delta(self, delta):
        """
        applies given delta to a given ctx data dictionary and returns
        the updated dictionary
        Updates ctx if successful, throws on failure.

        :param delta: a delta between current and new data
        :return: updated dictionary,
        """
        new_data, new_hash, hash_algo = DeltaProtocol.apply_delta(
            delta, self.data, self.sig, self.sig_algo
        )
        # save a copy of new data, it belongs to a caller & may be modified
        # later unpredictably invalidating our signature and state
        self.data = copy.deepcopy(new_data)
        self.sig = new_hash
        self.sig_algo = hash_algo
        return new_data

    def compare(self, ctx):
        """
        compares ctx signatures
        Args:
            ctx: DeltaProtocolCtx to compare

        Returns: True if ctx signature is non empty/initialized & equal self's
                 signature, False otherwise
        """
        if ctx and ctx.sig and ctx.sig_algo:
            return ctx.sig_algo == self.sig_algo and ctx.sig == self.sig
        return False

    @staticmethod
    def create_from_dict(ctx_dict):
        if isinstance(ctx_dict, dict):
            return DeltaProtocolCtx(
                None,
                ctx_dict.get(DeltaProtocol.CTX_HASH_KEY),
                ctx_dict.get(DeltaProtocol.SIG_ALG_KEY)
            )
        return DeltaProtocolCtx(sig_algo=None)
