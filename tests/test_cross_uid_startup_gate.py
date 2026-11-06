"""Preflight gate tests: reject unsafe secrets before binding transport."""
import os
import tempfile
import unittest

from agency.cross_uid_listener import serve_cross_uid_once


class CrossUidStartupGateTests(unittest.TestCase):
    def test_unsafe_database_denied_before_socket_creation(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            private = os.path.join(root, "private")
            os.mkdir(private, 0o700)
            keys = os.path.join(private, "keys")
            os.mkdir(keys, 0o700)
            db = os.path.join(private, "state.db")
            with open(db, "wb"):
                pass
            os.chmod(db, 0o644)
            transport = os.path.join(root, "transport")
            os.mkdir(transport, 0o710)
            sock = os.path.join(transport, "trusted.sock")
            with self.assertRaises(PermissionError):
                serve_cross_uid_once(
                    sock, object(), frozenset({os.geteuid() + 1}),
                    os.getegid(), acknowledged=True,
                    trusted_state=(private, db, keys)
                )
            self.assertFalse(os.path.lexists(sock))

    def test_missing_private_state_denied_before_bind(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            transport = os.path.join(root, "transport")
            os.mkdir(transport, 0o710)
            sock = os.path.join(transport, "trusted.sock")
            with self.assertRaises(FileNotFoundError):
                serve_cross_uid_once(
                    sock, object(), frozenset({os.geteuid() + 1}),
                    os.getegid(), trusted_state=(
                        os.path.join(root, "missing"), os.path.join(root, "missing", "db"),
                        os.path.join(root, "missing", "keys")
                    )
                )
            self.assertFalse(os.path.lexists(sock))

    def test_invalid_state_tuple_denied(self):
        with self.assertRaises(ValueError):
            serve_cross_uid_once(
                "/no/socket", object(), frozenset({os.geteuid() + 1}),
                os.getegid(), trusted_state=("/tmp",)
            )
