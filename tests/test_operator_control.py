"""Operator-only IPC security tests; no root access or live service required."""
import json
import unittest
from unittest.mock import Mock, patch

from agency.operator_control import (
    parse_operator_request, handle_operator_connection, dispatch_operator,
)


def request(action="approve"):
    fields = {
        "action": action,
        "approval_id": "approval-id",
        "operator_secret_hex": "ab" * 32,
    }
    if action == "approve_and_execute":
        fields.update({
            "task_id": "task-id",
            "job": "noop",
            "worker_credential": "test-credential",
            "lease_token": "lease-token",
        })
    return fields


class OperatorControlTests(unittest.TestCase):
    def test_strict_approve_request(self):
        self.assertEqual(
            parse_operator_request(json.dumps(request()).encode()), request()
        )

    def test_strict_execute_request(self):
        self.assertEqual(
            parse_operator_request(
                json.dumps(request("approve_and_execute")).encode()
            ), request("approve_and_execute")
        )

    def test_extra_worker_capability_field_denied(self):
        changed = request()
        changed["issue_credential"] = True
        with self.assertRaises(PermissionError):
            parse_operator_request(json.dumps(changed).encode())

    def test_arbitrary_command_denied_at_schema(self):
        changed = request("approve_and_execute")
        changed["command"] = "/bin/sh"
        with self.assertRaises(PermissionError):
            parse_operator_request(json.dumps(changed).encode())

    def test_oversized_and_malformed_requests_denied(self):
        for payload in (b"", b"{}",
                        b"{" + b"x" * 13000 + b"}",
                        b"not-json", b'{"action":"execute"}'):
            with self.subTest(payload=payload[:12]):
                with self.assertRaises(PermissionError):
                    parse_operator_request(payload)

    def test_operator_secret_must_be_32_raw_bytes_in_hex(self):
        changed = request()
        changed["operator_secret_hex"] = "00" * 16
        with self.assertRaises(PermissionError):
            parse_operator_request(json.dumps(changed).encode())

    def test_worker_peer_denied_before_receiving_payload(self):
        connection = Mock()
        with patch("agency.operator_control.peer_credentials",
                   return_value={"uid": 1002}):
            self.assertEqual(handle_operator_connection(
                connection, Mock(), ("operator", b"s" * 16, b"v" * 32),
                "/broker/key", "/broker/sock"
            ), "denied")
        connection.recv.assert_not_called()
        connection.sendall.assert_called_once_with(b'{"status": "denied"}\n')

    def test_verified_root_peer_and_secret_approve(self):
        connection = Mock()
        connection.recv.return_value = json.dumps(request()).encode() + b"\n"
        boundary = Mock()
        with patch("agency.operator_control.peer_credentials",
                   return_value={"uid": 0}):
            self.assertEqual(handle_operator_connection(
                connection, boundary, ("operator", b"s" * 16, b"v" * 32),
                "/broker/key", "/broker/sock"
            ), "accepted")
        boundary.approve_operator_request.assert_called_once_with(
            "approval-id", bytes.fromhex("ab" * 32), "operator",
            b"s" * 16, b"v" * 32,
        )
        boundary.execute_operator_approved_job.assert_not_called()

    def test_operator_authenticated_before_broker_execution(self):
        boundary = Mock()
        dispatch_operator(
            boundary, request("approve_and_execute"),
            ("operator", b"s" * 16, b"v" * 32),
            "/broker/key", "/broker/sock",
        )
        boundary.approve_operator_request.assert_called_once()
        boundary.execute_operator_approved_job.assert_called_once_with(
            "approval-id", "task-id", "noop", "test-credential",
            "lease-token", "/broker/key", "/broker/sock",
        )

    def test_wrong_secret_prevents_broker_attempt(self):
        boundary = Mock()
        boundary.approve_operator_request.side_effect = PermissionError("bad")
        connection = Mock()
        connection.recv.return_value = json.dumps(
            request("approve_and_execute")
        ).encode() + b"\n"
        with patch("agency.operator_control.peer_credentials",
                   return_value={"uid": 0}):
            self.assertEqual(handle_operator_connection(
                connection, boundary, ("operator", b"s" * 16, b"v" * 32),
                "/broker/key", "/broker/sock"
            ), "denied")
        boundary.execute_operator_approved_job.assert_not_called()


if __name__ == "__main__":
    unittest.main()
