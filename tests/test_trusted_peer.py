import os
import socket
import unittest
from unittest.mock import Mock

from agency.trusted_peer import peer_credentials, serve_authenticated_peer


class TrustedPeerTests(unittest.TestCase):
    def test_kernel_peer_uid(self):
        a, b = socket.socketpair()
        try:
            identity = peer_credentials(a)
            self.assertEqual(identity["uid"], os.getuid())
            self.assertGreater(identity["pid"], 0)
        finally:
            a.close()
            b.close()

    def test_denied_uid_does_not_process_payload(self):
        a, b = socket.socketpair()
        try:
            boundary = Mock()
            with self.assertRaises(PermissionError):
                serve_authenticated_peer(a, boundary, frozenset({os.getuid() + 1}))
            boundary.submit_stage.assert_not_called()
        finally:
            a.close()
            b.close()

    def test_empty_allowlist_denied(self):
        a, b = socket.socketpair()
        try:
            with self.assertRaises(ValueError):
                serve_authenticated_peer(a, Mock(), frozenset())
        finally:
            a.close()
            b.close()

    def test_non_socket_denied(self):
        with self.assertRaises(PermissionError):
            peer_credentials(object())
