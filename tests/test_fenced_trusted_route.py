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

    @patch("agency.fenced_trusted_route.operator_admission_lease")
    @patch("agency.fenced_trusted_route.os.geteuid", return_value=1000)
    @patch.object(TrustedAgentExecution, "execute_operator_approved_job")
    def test_delegates_only_to_existing_approval_boundary(self, execute, _uid, lease):
        boundary = object.__new__(TrustedAgentExecution)
        execute.return_value = {"exit_code": 0}
        result = execute_fenced_approved_job(
            boundary, "a", "t", "noop", "w", "l",
            broker_key_path="/etc/hermes-broker/signing.key",
            broker_socket_path="/run/hermes-broker/fenced-candidate.sock")
        lease.assert_called_once_with()
        self.assertEqual(result, {"exit_code": 0})
        execute.assert_called_once_with(
            "a", "t", "noop", "w", "l",
            "/etc/hermes-broker/signing.key",
            "/run/hermes-broker/fenced-candidate.sock")

    @patch("agency.fenced_trusted_route.operator_admission_lease")
    @patch("agency.fenced_trusted_route.os.geteuid", return_value=1000)
    @patch.object(TrustedAgentExecution, "execute_operator_approved_job")
    def test_exclusive_drain_denies_before_grant(self, execute, _uid, lease):
        boundary = object.__new__(TrustedAgentExecution)
        lease.return_value.__enter__.side_effect = PermissionError("maintenance")
        with self.assertRaises(PermissionError):
            execute_fenced_approved_job(
                boundary, "a", "t", "noop", "w", "l",
                broker_key_path="/etc/hermes-broker/signing.key",
                broker_socket_path="/run/hermes-broker/fenced-candidate.sock")
        execute.assert_not_called()

    @patch("agency.fenced_trusted_route.operator_admission_lease")
    @patch("agency.fenced_trusted_route.os.geteuid", return_value=1000)
    @patch.object(TrustedAgentExecution, "execute_operator_approved_job")
    def test_lease_covers_entire_execution(self, execute, _uid, lease):
        boundary = object.__new__(TrustedAgentExecution)
        def verify_held(*args):
            lease.return_value.__enter__.assert_called_once()
            lease.return_value.__exit__.assert_not_called()
            return {"exit_code": 0}
        execute.side_effect = verify_held
        execute_fenced_approved_job(
            boundary, "a", "t", "noop", "w", "l",
            broker_key_path="/etc/hermes-broker/signing.key",
            broker_socket_path="/run/hermes-broker/fenced-candidate.sock")
        lease.return_value.__exit__.assert_called_once()

if __name__ == "__main__":
    unittest.main()
