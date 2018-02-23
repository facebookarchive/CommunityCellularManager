"""
Some basic CRDT libraries.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import json

NAME = None
try:
    import snowflake
    NAME = snowflake.snowflake()
except Exception:
    pass

# snowflake sometimes fails silently, if so
# (or if not loaded) use UUID -kurtis
if not NAME:
    import uuid
    NAME = str(uuid.uuid4())


class StateCRDT(object):
    """
    This class represents a state-based CRDT, or convergent replicated data
    type. See http://hal.upmc.fr/inria-00555588/document for more information;
    all CDRTs defined here are based on definitions in this paper.

    The "state" of the StateCRDT is a json-able object.
    """

    def __init__(self, name=None):
        if name:
            self.name = name
        else:
            self.name = NAME
        self._state = None

    @classmethod
    def merge(cls, x, y):
        raise NotImplementedError

    @classmethod
    def from_state(cls, state, *args, **kwargs):
        """
        Create a CRDT from a given state.
        """
        raise NotImplementedError

    def get_state(self):
        return self._state

    def set_state(self, value):
        self._state = value

    state = property(get_state, set_state)

    def value(self):
        raise NotImplementedError

    def is_used(self):
        """
        Tests if this CRDT has been used (incremented or decremented)
        """
        raise NotImplementedError

    def serialize(self):
        """
        Return a JSON representation of the state of this CRDT
        """
        return json.dumps(self.state)


class GCounter(StateCRDT):
    """
    The GCounter is an increment-only counter.
    """
    def __init__(self, name=None):
        super(GCounter, self).__init__(name)
        self._state = {self.name: 0}

    def increment(self, amount=1):
        if abs(amount) != amount:
            raise ValueError("GCounter is increment-only, must use positive value")
        self.state[self.name] += amount

    def value(self):
        """
        Returns an integer value of this counter.
        """
        return sum(self.state.values())

    def is_used(self):
        for s in self.state.keys():
            if (self.state[s] != 0):
                return True
        return False

    @classmethod
    def merge(cls, x, y, name=None):
        """
        Return an object that reflects the merged state of the two CRDTs.

        For each key, in each, return the max value of the two.
        """
        keys = set(set(x.state.keys()) | set(y.state.keys()))
        z = {
            k: max(x.state.get(k, 0), y.state.get(k, 0)) for k in keys
        }
        return GCounter.from_state(z, name=name)

    @classmethod
    def from_state(cls, state, name=None):
        def max_int(k, a, b):
            """ Get the max value of a key from two counters """
            a_val = a.get(k, 0)
            if not isinstance(a_val, int):
                raise ValueError("expected int, got '%s'" % (a_val, ))
            b_val = b.get(k, 0)
            if not isinstance(b_val, int):
                raise ValueError("expected int, got '%s'" % (b_val, ))
            return max(a_val, b_val)

        new = GCounter(name=name)
        try:
            keys = set(set(new.state.keys()) | set(state.keys()))
            new.state = {
                k: max_int(k, new.state, state) for k in keys
            }
        except Exception:
            raise ValueError("Invalid state for GCounter")
        return new


class PNCounter(StateCRDT):
    """
    A PNCounter is a counter that can be incremented or decremented.
    Internally, it's a combination of two GCounters (one for increments and one
    for decrements).
    """
    def __init__(self, name=None):
        super(PNCounter, self).__init__(name)
        self.P = GCounter(self.name)
        self.N = GCounter(self.name)
        self._state = {"p": self.P.state, "n": self.N.state}

    def get_state(self):
        return {"p": self.P.state, "n": self.N.state}
    state = property(get_state)

    def increment(self, amount=1):
        self.P.increment(amount)

    def decrement(self, amount=1):
        self.N.increment(amount)

    def value(self):
        return self.P.value() - self.N.value()

    #returns true if all counts in crdt are 0
    def is_used(self):
        return self.P.is_used() or self.N.is_used()

    @classmethod
    def merge(cls, x, y, name=None):
        """
        Returns an object that reflects the merged state of the two CRDTs.
        """
        newP = GCounter.merge(x.P, y.P, name=name)
        newN = GCounter.merge(x.N, y.N, name=name)
        new_state = {"p": newP.state, "n": newN.state}
        return PNCounter.from_state(new_state, name=name)

    @classmethod
    def from_state(cls, state, name=None):
        new = PNCounter(name=name)
        try:
            new.P = GCounter.from_state(state['p'], name=new.name)
            new.N = GCounter.from_state(state['n'], name=new.name)
        except Exception:
            raise ValueError("Invalid state for PN counter")
        return new

    @classmethod
    def from_json(cls, jstate, name=None):
        """ Convenience method for common case of loading from JSON. """
        return cls.from_state(json.loads(jstate), name)
