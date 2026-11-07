"""Security tests for the non-worker fenced approved-job routing seam."""
import unittest
from unittest.mock import patch

from agency.fenced_trusted_route import execute_fenced_approved_job
from agency.trusted_execution import TrustedAgentExecution

class FencedTrustedRouteTests(unittest.TestCase):
    def test_rejects_untrusted_boundary(self):
        with self.assertRaises(TypeError):
            execute_fenced_approved_job(object(), "a", "t", "noop", "w", "l",
                broker_key_path="/etc/hermes-broker/signing.key",
                broker_socket_path="/run/hermes-broker/fenced-candidate.sock")

    @patch("agency.fenced_trusted_route.os.geteuid", return_value=1000)
    def test_rejects_unapproved_endpoint(self, _uid):
        boundary = object.__new__(TrustedAgentExecution)
        with self.assertRaises(PermissionError):
            execute_fenced_approved_job(boundary, "a", "t", "noop", "w", "l",
                broker_key_path="/etc/hermes-broker/signing.key",
                broker_socket_path="/run/hermes-broker/broker.sock")

    @patch("agency.fenced_trusted_route.os.geteuid", return_value=0)
    def test_rejects_root_caller(self, _uid):
        boundary = object.__new__(TrustedAgentExecution)
        with self.assertRaises(PermissionError):
            execute_fenced_approved_job(boundary, "a", "t", "noop", "w", "l",
                broker_key_path="/etc/hermes-broker/signing.key",
                broker_socket_path="/run/hermes-broker/fenced-candidate.sock")

    @patch("agency.fenced_trusted_route.os.geteuid", return_value=1000)
    @patch.object(TrustedAgentExecution, "execute_operator_approved_job")
    def test_delegates_only_to_existing_approval_boundary(self, execute, _uid):
        boundary = object.__new__(TrustedAgentExecution)
        execute.return_value = {"exit_code": 0}
        result = execute_fenced_approved_job(
            boundary, "a", "t", "noop", "w", "l",
            broker_key_path="/etc/hermes-broker/signing.key",
            broker_socket_path="/run/hermes-broker/fenced-candidate.sock")
        self.assertEqual(result, {"exit_code": 0})
        execute.assert_called_once_with(
            "a", "t", "noop", "w", "l",
            "/etc/hermes-broker/signing.key",
            "/run/hermes-broker/fenced-candidate.sock")

if __name__ == "__main__":
    unittest.main()
