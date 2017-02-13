"""
XML CDR generators (for testing purposes).

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

import abc
from random import randrange
import six
import xml.dom

# The Freeswitch XML CDR format contains a lot of data that isn't used by CCM.
# CCM's CDR parsing is done by searching for specific tags, so CDR structure
# doesn't matter, just that the expected tags are present. Hence a 'flat' XML
# document, with just a single 'cdr' element, suffices for testing purposes.
#
# The required tags are context-specific: cloud or client, voice or SMS.


@six.add_metaclass(abc.ABCMeta)
class XmlCdr(dict):
    """Base XML-CDR class. Stores initialiser args as tags."""
    def __init__(self, **kwargs):
        super(XmlCdr, self).__init__(kwargs)

    @abc.abstractmethod
    def required_tags(self):
        """Get the set of tags required for a particular type of CDR.

        Returns:
            List of pairs (tag, default_or_type), where <tag> is the
            name of a required tag, and <default_or_type> is either a
            default value or the type of a tag that must be non-empty.
        """
        pass

    @property
    def xml(self):
        """Create the XML representation of this type of CDR."""
        doc = xml.dom.getDOMImplementation().createDocument(
            xml.dom.EMPTY_NAMESPACE, "cdr", None)
        cdr = doc.childNodes[0]
        for k, default_or_type in self.required_tags():
            v = self.get(k, default_or_type)
            if isinstance(v, type):  # no default - required argument
                raise ValueError("missing tag: " + k)
            elem = doc.createElement(k)
            elem.appendChild(doc.createTextNode(str(v)))
            cdr.appendChild(elem)
        return doc

    @staticmethod
    def _get_text(nodes):
        """Get the text value of an XML tag (from the minidom doc)."""
        rc = []
        for node in nodes:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        return ''.join(rc)

    @classmethod
    def from_xml(cls, src):
        """Generate instance of subclass from an XML string."""
        dom = xml.dom.minidom.parseString(src)
        # Make sure all of the necessary pieces are there.  Fail if any
        # required tags are missing
        xc = cls()
        for tag_name, default_or_type in xc.required_tags():
            elem = dom.getElementsByTagName(tag_name)
            if not elem:
                raise ValueError("Missing XML tag: " + tag_name)
            tag_type = (default_or_type
                        if isinstance(default_or_type, type)
                        else type(default_or_type))
            xc[tag_name] = tag_type(cls._get_text(elem[0].childNodes))
        return xc


class CloudVoiceCdr(XmlCdr):
    def __init__(self, **kwargs):
        super(CloudVoiceCdr, self).__init__(**kwargs)

    def required_tags(self):
        # For cloud voice calls the required tags are
        # (per endagaweb.internalapi.BillVoice.post):
        #  * billsec (call duration)
        #  * destination_number (MSISDN)
        #  * caller_id_name (MSISDN)
        #  * network_addr (required but ignored by cloud API)
        #  * username (required but ignored by cloud API)
        # MSISDN values must include country code, leading '+' is unnecessary
        # and will be stripped.
        return [
            ("billsec", int),
            ("caller_id_name", str),
            ("destination_number", str),
            ("network_addr", "."),
            ("username", "."),
        ]


def gen_number(digits, prefix):
    """ Helper function to generate a random MSISDN. """
    return prefix + ("%099d" % (randrange(0, 10 ** digits), ))[-digits:]
