"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import logging
import struct

from enum import IntEnum, unique

from ..crypto.utils import CryptoError
from ..store.base import SubscriberNotFoundError


@unique
class MsgType(IntEnum):
    """
    GSUP message types.
    Lets support different types of subscriber deletion messages when needed.
    """
    UPDATE_LOCATION_REQ = 0x04  # From peer
    UPDATE_LOCATION_ERR = 0x05
    UPDATE_LOCATION_RES = 0x06
    SEND_AUTH_INFO_REQ = 0x08  # From peer
    SEND_AUTH_INFO_ERR = 0x09
    SEND_AUTH_INFO_RSP = 0x0a
    AUTH_FAILURE_REPORT = 0x0b  # From peer
    INSERT_SUBS_DATA_REQ = 0x10
    INSERT_SUBS_DATA_ERR = 0x11  # From peer
    INSERT_SUBS_DATA_RES = 0x12  # from peer


@unique
class IEType(IntEnum):
    """
    GSUP Information Element types.
    """
    # IEs that are encoded directly in messages
    IMSI = 0x01
    CAUSE = 0x02
    AUTH_TUPLE = 0x03
    CN_DOMAIN = 0x28
    PDP_INFO_COMPLETE = 0x04
    PDP_INFO = 0x05

    # IEs which are encoded into other IEs
    RAND = 0x20
    SRES = 0x21
    KC_KEY = 0x22
    PDP_CONTEXT_ID = 0x10
    PDP_TYPE = 0x11
    APN_NAME = 0x12


@unique
class IEPresence(IntEnum):
    """
    Provides info about the requirement of an IE for a message
    """
    MANDATORY = 1
    OPTIONAL = 2


@unique
class ErrorCauseType(IntEnum):
    """
    Possible values in the Cause IE
    """
    IMSI_UNKNOWN = 0x02
    NETWORK_FAILURE = 0x11
    PROTOCOL_ERR = 0x6f


class GSUPCodecError(Exception):
    """
    Exception class used for encoder or decoder errors.
    """
    pass


class InformationElement:
    """
    Class to hold info about the format of an IE.
    """
    def __init__(self, min_length, max_length, decoder_fn, encoder_fn):
        self.min_length = min_length
        self.max_length = max_length
        self._decoder_fn = decoder_fn
        self._encoder_fn = encoder_fn

    def encode(self, val, buf, offset):
        """
        Encode the IE into the buf at offset.

        Returns:
            int: length of encoded bytes
        Raises:
            GSUPCodecError on failure
        """
        return self._encoder_fn(
            val, buf, offset,
            self.min_length, self.max_length)

    def decode(self, val):
        """
        Returns:
            the decoded value of the IE.
        Raises:
            GSUPCodecError on failure
        """
        if len(val) < self.min_length or len(val) > self.max_length:
            raise GSUPCodecError(
                "IE length not in range: %d (%d-%d), val: %s"
                % (len(val), self.min_length, self.max_length, val))

        return self._decoder_fn(val)

    @staticmethod
    def decode_imsi(val):
        """
        Decode the IMSI bytes into string.

        Each byte has 2 digits encoded like
            digit N: 0-3 bits, digit N-1: 4-7 bits
        If the length is odd, then the last bytes is encoded as
            1111, Last digit: 4-7 bits
        """
        imsi = ""
        byt = 0
        for byt in val:
            imsi += str(byt & 0x0f)
            if (byt >> 4) != 0x0f:
                imsi += str(byt >> 4 & 0x0f)
        return imsi

    @staticmethod
    def encode_imsi(val, buf, offset, min_len, max_len):
        """
        Encode the string IMSI into bytes.
        """
        if not val.isdigit():
            raise GSUPCodecError("IMSI has non-digits: %s" % val)
        length = int((len(val)+1)/2)  # round down for odd
        if length < min_len or length > max_len:
            raise GSUPCodecError("Invalid IMSI length: %s" % val)
        for i in range(length):
            digit1 = int(val[2*i]) & 0x0f
            if 2*i+1 < len(val):
                digit2 = (int(val[2*i+1]) << 4) & 0xf0
            else:
                digit2 = 0xf0
            buf[offset + i] = digit1 | digit2
        return length

    @staticmethod
    def decode_bytes(val):
        """
        Convert the memoryview into bytes
        """
        return val.tobytes()

    @staticmethod
    def encode_bytes(val, buf, offset, min_len, max_len):
        """
        Encode the bytes into the buf at the specified offset.
        """
        length = len(val)
        if length < min_len or length > max_len:
            raise GSUPCodecError("Invalid length for bytes IE")
        buf[offset:offset + length] = val
        return length

    @staticmethod
    def decode_num(val):
        """
        Decode the single byte value
        """
        return val[0]

    @staticmethod
    # pylint: disable=unused-argument
    def encode_num(val, buf, offset, min_len, max_len):
        """
        Encode a single byte value
        """
        buf[offset] = val
        return 1

    @staticmethod
    def decode_auth_tuple(val):
        """
        Decode the Auth tuple IE.

        Args:
            v: bytes of encoded auth tuple
        Returns:
            Map containing (rand, sres, kc) elements
        """
        (_, _, rand, _, _, sres, _, _, key) = struct.unpack(
            '2B16s2B4s2B8s', val)
        return (rand, sres, key)

    @staticmethod
    # pylint: disable=unused-argument
    def encode_auth_tuple(val, buf, offset, min_len, max_len):
        """
        Encode the Auth tuple IE.

        Args:
            val: (rand, sres, kc) tuple
        Returns:
            The size of encoded auth tuple (always 34)
        """
        (rand, sres, key) = val
        if len(rand) != 16 or len(sres) != 4 or len(key) != 8:
            raise GSUPCodecError(
                "Bad auth tuple to encode: rand: %s, sres: %s, key: %s"
                % (rand, sres, key))
        struct.pack_into(
            '2B16s2B4s2B8s', buf, offset,
            IEType.RAND, 16, rand, IEType.SRES, 4, sres,
            IEType.KC_KEY, 8, key)
        return 34

    @staticmethod
    # pylint: disable=unused-argument
    def encode_pdp_info(val, buf, offset, min_len, max_len):
        """
        Encode the PDP info. By default we just encode the APN
        as '*' for the subscriber to allow all APNs.
        """
        fmt = '11B'
        struct.pack_into(
            fmt, buf, offset,
            IEType.PDP_CONTEXT_ID, 1, 1,
            IEType.PDP_TYPE, 2, 0x1, 0x21,
            IEType.APN_NAME, 2, 1, 0x2A)
        return 11


class GPRSSubcriberUpdateProtocol:
    """
    GPRSSubcriberUpdateProtocol (GSUP) is a protocol used by Osmo for
    communicating with a HLR like entity. GSUP is a simplified version of
    3GPP MAP, which uses TLV instead of the ASN.1 encoding format.
    """
    def __init__(self):
        # _msg_fmts contains the map of valid IEs for each message type
        # msgtype: List of (ietype, iepresence) tuples
        self._msg_fmts = {
            MsgType.UPDATE_LOCATION_REQ:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.CN_DOMAIN, IEPresence.OPTIONAL)],
            MsgType.UPDATE_LOCATION_ERR:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.CAUSE, IEPresence.MANDATORY)],
            MsgType.UPDATE_LOCATION_RES:
                [(IEType.IMSI, IEPresence.MANDATORY)],
            MsgType.SEND_AUTH_INFO_REQ:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.CN_DOMAIN, IEPresence.OPTIONAL)],
            MsgType.SEND_AUTH_INFO_ERR:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.CAUSE, IEPresence.MANDATORY)],
            MsgType.SEND_AUTH_INFO_RSP:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.AUTH_TUPLE, IEPresence.OPTIONAL)],
            MsgType.AUTH_FAILURE_REPORT:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.CN_DOMAIN, IEPresence.OPTIONAL)],
            MsgType.INSERT_SUBS_DATA_REQ:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.CN_DOMAIN, IEPresence.OPTIONAL),
                 (IEType.PDP_INFO_COMPLETE, IEPresence.OPTIONAL),
                 (IEType.PDP_INFO, IEPresence.OPTIONAL)],
            MsgType.INSERT_SUBS_DATA_ERR:
                [(IEType.IMSI, IEPresence.MANDATORY),
                 (IEType.CAUSE, IEPresence.MANDATORY)],
            MsgType.INSERT_SUBS_DATA_RES:
                [(IEType.IMSI, IEPresence.MANDATORY)],
            }
        # _ie_fmts contains the info to encode/decode an IE
        # ietype: InformationElement(
        #    min length, max length,
        #    decoder fn,
        #    encoder fn
        # )
        self._ie_fmts = {
            IEType.IMSI: InformationElement(
                0, 8,
                InformationElement.decode_imsi,
                InformationElement.encode_imsi),
            IEType.CAUSE: InformationElement(
                1, 1,
                InformationElement.decode_num,
                InformationElement.encode_num),
            IEType.AUTH_TUPLE: InformationElement(
                34, 34,
                InformationElement.decode_auth_tuple,
                InformationElement.encode_auth_tuple),
            IEType.CN_DOMAIN: InformationElement(
                1, 1,
                InformationElement.decode_num,
                InformationElement.encode_num),
            IEType.PDP_INFO_COMPLETE: InformationElement(
                0, 0,
                InformationElement.decode_bytes,
                InformationElement.encode_bytes),
            IEType.PDP_INFO: InformationElement(
                10, 109,
                InformationElement.decode_bytes,
                InformationElement.encode_pdp_info),
            }

    def decode(self, msg):
        """
        Decode the msg bytes into its individual IEs.

        Args:
            msg (bytes): contains the bytes of the entire message
        Returns:
            (msgtype, iemap) tuple.
            msgtype (MsgType): enum specifying message type
            iemap (map): IEType -> val map
        Raises:
            GSUPCodecError if decoding fails
        """
        if len(msg) == 0:
            raise GSUPCodecError("Zero length GSUP msg")

        if msg[0] not in self._msg_fmts:
            raise GSUPCodecError("Unknown GSUP msg: %s" % msg.tobytes())
        msg_type = MsgType(msg[0])

        ies = {}
        offset = 1
        while (offset + 1) < len(msg):  # type and length available
            ie_length = msg[offset + 1]
            if msg[offset] not in self._ie_fmts:
                logging.warning("Unknown IE: 0x%x, GSUP msg: %s",
                                msg[offset], msg.tobytes())
                # Optional IEs could be ignored. We would validate for
                # absence of mandatory IEs later.
                offset += ie_length + 2
                continue
            ie_type = IEType(msg[offset])
            offset += 2

            if (offset + ie_length) > len(msg):
                raise GSUPCodecError(
                    "Invalid IE length: %d, name: %s, GSUP msg: %s"
                    % (ie_length, ie_type, msg.tobytes()))

            ies[ie_type] = self._ie_fmts[ie_type].decode(
                msg[offset:offset+ie_length])
            offset += ie_length

        self._validate_msg(msg_type, ies)

        logging.debug("Received GSUP msg: > %s, IEs: %s", msg_type, ies)
        return (msg_type, ies)

    def get_max_bytes(self, ies):
        """
        Get the maximum bytes that would be required to encode the IEs.

        Args:
            ies (map): IEType -> val map
        Returns:
            Size
        """
        size = 1
        for (ie_type, _) in ies.items():
            size += self._ie_fmts[ie_type].max_length + 2
        return size

    def encode(self, buf, offset, msg_type, ies):
        """
        Encodes the GSUP msg into the buf at the specified offset. Requires
        the sufficient memory to be allocated before hand by calling
        get_max_bytes().

        Args:
            buf (memoryview): Output buffer
            offset (int): starts the encoding at offset in buf
            msg_type (MsgType): as the name implies
            ies (map): IEType -> val map
        Returns:
            Encoded size.
        Raises:
            GSUPCodecError on failure.
        """
        logging.debug("Encoding GSUP msg: < %s, IEs: %s", msg_type, ies)

        self._validate_msg(msg_type, ies)

        buf[offset] = msg_type
        offset += 1

        for (ie_type, ie_val) in ies.items():
            buf[offset] = ie_type
            ie_len = self._ie_fmts[ie_type].encode(ie_val, buf, offset + 2)
            buf[offset + 1] = ie_len
            offset += 2 + ie_len
        return offset

    def _validate_msg(self, msg_type, ies_present):
        """
        Check if all mandatory IEs are present

        Args:
            msg_type (MsgType): message type to validate
            ies_present (map): IEType -> val map for IEs present in msg
        Returns:
            bool: True if msg is valid
        """
        msg_ies = self._msg_fmts[msg_type]
        for (ie_type, presence) in msg_ies:
            if presence == IEPresence.MANDATORY and ie_type not in ies_present:
                raise GSUPCodecError(
                    "Mandatory IE (%s) not present in msg: %s"
                    % (ie_type, msg_type))


# Create one global instance of the protocol
_GSUP = GPRSSubcriberUpdateProtocol()


class GSUPManager:
    """
    GSUPManager interfaces with the IPA layer and decodes/encodes the
    messages using the GPRSSubcriptionProtocol class.

    The manager also speaks to the store to lookup the subscriber info,
    and responds to queries from peers.
    """

    def __init__(self, gsm_processor, ipa_writer):
        self._gsm_processor = gsm_processor
        self._ipa_writer = ipa_writer

    def handle_msg(self, msg):
        """
        Handle the msg bytes from the IPA layer
        """
        try:
            (msg_type, ies) = _GSUP.decode(msg)
        except GSUPCodecError as err:
            # Decode failure. Log and continue with next message.
            logging.exception("Decoding failed with err: %s", err)
            return

        if msg_type == MsgType.SEND_AUTH_INFO_REQ:
            self._msg_send_auth_info_req(ies)
        elif msg_type == MsgType.AUTH_FAILURE_REPORT:
            self._msg_auth_failure_report(ies)
        elif msg_type == MsgType.UPDATE_LOCATION_REQ:
            self._msg_update_location_req(ies)
        elif msg_type == MsgType.INSERT_SUBS_DATA_RES:
            self._msg_insert_subs_data_resp(ies)
        elif msg_type == MsgType.INSERT_SUBS_DATA_ERR:
            self._msg_insert_subs_data_err(ies)
        else:
            logging.warning("Unhandled message: %s, IEs: %s", msg_type, ies)

    def send_msg(self, msg_type, ies):
        """
        Encodes and sends the message to the IPA layer.
        """
        # Calc the maximum length possible for the message, and allocate memory
        buf_size = _GSUP.get_max_bytes(ies)
        (buf, offset) = self._ipa_writer.get_write_buf(buf_size)

        try:
            msg_len = _GSUP.encode(buf, offset, msg_type, ies)
        except GSUPCodecError as err:
            # Encoding should always succeed
            logging.fatal(
                "Encoding failed with err: %s, for msg: %s, ies: %s",
                err, msg_type, ies)
            return

        # Reset the length in the IPA header based on actual msg size
        self._ipa_writer.reset_length(buf, msg_len - offset)

        # Write the encoded msg
        self._ipa_writer.write(buf[:msg_len])

    def _msg_send_auth_info_req(self, req_ies):
        imsi = req_ies[IEType.IMSI]
        resp_ies = {IEType.IMSI: imsi}

        try:
            (rand, sres, key) = self._gsm_processor.get_gsm_auth_vector(imsi)
        except CryptoError as err:
            logging.error("Auth error for %s: %s", imsi, err)
            resp_ies[IEType.CAUSE] = ErrorCauseType.NETWORK_FAILURE
            self.send_msg(MsgType.SEND_AUTH_INFO_ERR, resp_ies)
        except SubscriberNotFoundError:
            logging.warning("Auth error for %s: subscriber not found", imsi)
            resp_ies[IEType.CAUSE] = ErrorCauseType.IMSI_UNKNOWN
            self.send_msg(MsgType.SEND_AUTH_INFO_ERR, resp_ies)
        else:
            # All good. Send the Auth Info Response.
            logging.info("Successful auth for %s", imsi)
            resp_ies[IEType.AUTH_TUPLE] = (rand, sres, key)
            self.send_msg(MsgType.SEND_AUTH_INFO_RSP, resp_ies)

    # pylint: disable=no-self-use
    def _msg_auth_failure_report(self, req_ies):
        imsi = req_ies[IEType.IMSI]
        logging.info("Received Auth Failure Report for IMSI: %s", imsi)

    def _msg_update_location_req(self, req_ies):
        imsi = req_ies[IEType.IMSI]
        resp_ies = {
                IEType.IMSI: imsi,
                IEType.PDP_INFO_COMPLETE: bytes(),
                IEType.PDP_INFO: bytes(),
                }
        self.send_msg(MsgType.INSERT_SUBS_DATA_REQ, resp_ies)

    def _msg_insert_subs_data_resp(self, req_ies):
        imsi = req_ies[IEType.IMSI]
        resp_ies = {IEType.IMSI: imsi}
        self.send_msg(MsgType.UPDATE_LOCATION_RES, resp_ies)

    # pylint: disable=no-self-use
    def _msg_insert_subs_data_err(self, req_ies):
        logging.info("Received Auth Failure Report for IMSI: %s, cause: %d",
                     req_ies[IEType.IMSI], req_ies[IEType.CAUSE])
