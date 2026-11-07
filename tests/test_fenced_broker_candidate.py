"""Candidate broker fail-closed preflight tests without root or systemd."""
import unittest
from unittest.mock import patch

from agency.fenced_broker_candidate import _read_grant, serve_candidate


class CandidateBrokerTests(unittest.TestCase):
    @patch("agency.fenced_broker_candidate.socket.socket")
    @patch("agency.fenced_broker_candidate.read_broker_key")
    @patch("agency.fenced_broker_candidate.require_recovered",
           side_effect=PermissionError("Recovery pending"))
    @patch("agency.fenced_broker_candidate.verify_private_ledger")
    @patch("agency.fenced_broker_candidate.pwd.getpwuid")
    @patch("agency.fenced_broker_candidate.os.geteuid", return_value=0)
    def test_pending_recovery_blocks_socket_binding(
            self, _uid, identity, _ledger, _gate, _key, socket_factory):
        identity.return_value.pw_gid = 1001
        with self.assertRaisesRegex(PermissionError, "Recovery pending"):
            serve_candidate("/run/hermes-broker/fenced-candidate.sock",
                            1001, 1001, "/tmp/ledger", "/tmp/journal",
                            "/tmp/trusted.db", "/tmp/key")
        socket_factory.assert_not_called()

    def test_untrusted_peer_rejected_before_read(self):
        import socket
        import struct
        class Conn:
            def getsockopt(self, *_args):
                return struct.pack("3i", 1, 999, 999)
            def recv(self, *_args):
                raise AssertionError("Untrusted request read")
        with self.assertRaisesRegex(PermissionError, "Untrusted"):
            _read_grant(Conn(), 1001)


if __name__ == "__main__":
    unittest.main()
