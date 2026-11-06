import os
import unittest
from unittest.mock import patch

from agency.protected_service import serve_protected_once


class ProtectedServiceTests(unittest.TestCase):
    def test_root_rejected_before_any_socket(self):
        with patch("agency.protected_service.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                serve_protected_once(
                    "/unused.sock", object(), frozenset({1001}), 1002,
                    ("/private", "/private/db", "/private/keys")
                )

    def test_missing_state_rejected(self):
        with patch("agency.protected_service.os.geteuid", return_value=1001):
            with self.assertRaises(ValueError):
                serve_protected_once(
                    "/unused.sock", object(), frozenset({1002}), 1003, None
                )

    def test_same_uid_denied(self):
        with patch("agency.protected_service.os.geteuid", return_value=1001):
            with self.assertRaises(PermissionError):
                serve_protected_once(
                    "/unused.sock", object(), frozenset({1001}), 1003,
                    ("/private", "/private/db", "/private/keys")
                )

    def test_protected_state_required_before_listener(self):
        state = ("/private", "/private/db", "/private/keys")
        with (patch("agency.protected_service.os.geteuid", return_value=1001),
              patch("agency.protected_service.verify_private_state",
                    side_effect=PermissionError("unsafe")) as verify,
              patch("agency.protected_service.serve_cross_uid_once") as listener):
            with self.assertRaises(PermissionError):
                serve_protected_once(
                    "/unused.sock", object(), frozenset({1002}), 1003, state
                )
            verify.assert_called_once_with(*state)
            listener.assert_not_called()

    def test_verified_entrypoint_enforces_acknowledgement(self):
        state = ("/private", "/private/db", "/private/keys")
        boundary = object()
        with (patch("agency.protected_service.os.geteuid", return_value=1001),
              patch("agency.protected_service.verify_private_state",
                    return_value=True),
              patch("agency.protected_service.serve_cross_uid_once",
                    return_value="accepted") as listener):
            self.assertEqual(
                serve_protected_once(
                    "/unused.sock", boundary, frozenset({1002}), 1003, state
                ), "accepted"
            )
            listener.assert_called_once_with(
                "/unused.sock", boundary, frozenset({1002}), 1003,
                acknowledged=True, trusted_state=state
            )
