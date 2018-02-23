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

import collections
import json

import six

DIFF_ADD_TAG = '+'
DIFF_REMOVE_TAG = '-'


def diff(new, old):
    """
    Produces a diff (delta) between two dictionaries recursively, returns a
    tuple of elements to remove & add from/into 'old' dictionary to get 'new'
    dictionary.

    Args:
        new: new dictionary which should be a result of applaying delta to old
             dict
        old: old dictionary to apply the returned delta on in order to create
             the new dict

    Returns: delta to apply on old dictionary to make the new one
               ({ '+': ..., '-': ... })
             Both, '+' (add) & '-' (remove) keys are optional
             if old & new dictionaries are identical {} will be returned
             Throws TypeError if new or old are not valid dictionaries
    """
    if isinstance(new, dict) and isinstance(old, dict):
        toremove = {}
        toadd = {}
        for k, new_v in six.iteritems(new):
            old_v = old.get(k)
            if old_v is not None:
                if new_v != old_v:
                    if isinstance(new_v, dict) and isinstance(old_v, dict):
                        kdelta = diff(new_v, old_v)
                        if DIFF_REMOVE_TAG in kdelta:
                            toremove[k] = kdelta[DIFF_REMOVE_TAG]
                        if DIFF_ADD_TAG in kdelta:
                            toadd[k] = kdelta[DIFF_ADD_TAG]
                    elif isinstance(new_v, list) and isinstance(old_v, list):
                        toreml, toaddl = _diff_lists(new_v, old_v)
                        if toreml:
                            toremove[k] = toreml
                        if toaddl:
                            toadd[k] = toaddl
                    else:
                        # diff only performs deep analysis of dictionaries and
                        #  lists, anything else is treated as a single value
                        toadd[k] = new_v
            else:
                toadd[k] = new_v

        for k in old:
            if k not in new:
                toremove[k] = True
        delta = {}
        if toremove:
            delta[DIFF_REMOVE_TAG] = toremove
        if toadd:
            delta[DIFF_ADD_TAG] = toadd

        return delta

    raise TypeError("Both Parameters Must Be Dictionaries")


def apply_delta(old, delta):
    """
    Args:
        old: dictionary to apply delta on (old dictionary)
        delta: the delta to apply, delta can be
          1) empty: {} or
          2) { '+': ..., '-': ... }

    Returns:
        modified dictionary, modifies old dictionary in place
    """
    if delta and isinstance(delta, dict) and isinstance(old, dict):
        if DIFF_REMOVE_TAG in delta:
            old = _remove(old, delta[DIFF_REMOVE_TAG])
        if DIFF_ADD_TAG in delta:
            old = _add(old, delta[DIFF_ADD_TAG])
    return old


def _remove(old, rdelta):
    if isinstance(rdelta, dict):
        for k, rdelta_v in six.iteritems(rdelta):
            old_v = old.get(k)
            if old_v is not None:
                if rdelta_v is True:
                    del old[k]
                elif isinstance(rdelta_v, list) and isinstance(old_v, list):
                    for el in rdelta_v:
                        old_v.remove(el)
                else:
                    old[k] = _remove(old_v, rdelta_v)
    return old


def _add(old, adelta):
    if isinstance(adelta, dict):
        for k, adelta_v in six.iteritems(adelta):
            old_v = old.get(k)
            if old_v is not None:
                if isinstance(adelta_v, dict):
                    old[k] = _add(old_v, adelta_v)
                    continue
                elif isinstance(adelta_v, list) and isinstance(old_v, list):
                    for el in adelta_v:
                        old_v.append(el)
                    continue

            old[k] = adelta_v
    return old


def _diff_lists(new_list, old_list):
    nlist = collections.Counter((_make_hashable(el) for el in new_list))
    olist = collections.Counter((_make_hashable(el) for el in old_list))
    toreml = list((olist - nlist).elements())
    toaddl = list((nlist - olist).elements())
    return toreml, toaddl


def _uni_hash(self):
    try:
        return json.dumps(self, skipkeys=True, sort_keys=True).__hash__()
    except Exception:
        # all invalid objects will share a hash bucket
        return "Invalid Object's Hash".__hash__()


def _make_hashable(o):
    if isinstance(o, collections.Hashable):
        return o
    # Py2 requires string class name, not Unicode (which literals are)
    return type(str(''), (type(o),), dict(__hash__=_uni_hash))(o)
