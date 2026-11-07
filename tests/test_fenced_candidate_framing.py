"""Regression tests for strict signed request framing and trusted peer identity."""
import json
import socket
import struct
import unittest
from unittest.mock import patch

from agency.fenced_broker_candidate import _read_grant


class _FakeConn:
    def __init__(self, chunks, uid=1001):
        self.chunks = iter(chunks)
        self.uid = uid
    def getsockopt(self, *_args):
        return struct.pack("3i", 7, self.uid, 1001)
    def settimeout(self, _value):
        pass
    def recv(self, _size):
        return next(self.chunks, b"")


class CandidateFramingTests(unittest.TestCase):
    def test_one_valid_newline_terminated_grant(self):
        grant = {"id": "test"}
        self.assertEqual(_read_grant(_FakeConn([
            json.dumps({"grant": grant}).encode() + b"\n"
        ]), 1001), grant)

    def test_wrong_uid_rejected(self):
        with self.assertRaises(PermissionError):
            _read_grant(_FakeConn([b'{"grant":{}}\n'], uid=1002), 1001)

    def test_missing_newline_rejected(self):
        with self.assertRaises(PermissionError):
            _read_grant(_FakeConn([b'{"grant":{}}']), 1001)

    def test_multiple_messages_rejected(self):
        with self.assertRaises(PermissionError):
            _read_grant(_FakeConn([b'{"grant":{}}\n{"grant":{}}\n']), 1001)

    def test_unknown_request_field_rejected(self):
        with self.assertRaises(PermissionError):
            _read_grant(_FakeConn([b'{"grant":{},"job":"identity"}\n']), 1001)

    def test_untrusted_uid_never_reads_payload(self):
        conn = _FakeConn([b'{"grant":{}}\n'], uid=999)
        with patch.object(conn, "recv", side_effect=AssertionError("read")):
            with self.assertRaises(PermissionError):
                _read_grant(conn, 1001)


if __name__ == "__main__":
    unittest.main()
