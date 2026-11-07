"""Candidate endpoint routing is opt-in and stays under the operator lease."""
import unittest
from unittest.mock import Mock, patch

from agency.operator_control import dispatch_operator


class CandidateOperatorRouteTests(unittest.TestCase):
    def setUp(self):
        self.boundary = Mock()
        self.verifier = ("operator", b"salt", b"proof")
        self.request = {
            "action": "approve_and_execute",
            "approval_id": "approval",
            "operator_secret_hex": "a" * 64,
            "task_id": "task",
            "job": "noop",
            "worker_credential": "worker",
            "lease_token": "lease",
        }

    @patch("agency.operator_control.os.path.lexists", return_value=False)
    @patch("agency.operator_control.operator_admission_lease")
    def test_candidate_uses_existing_lease_and_pinned_key(self, lease, _freeze):
        def execute(*args):
            lease.return_value.__enter__.assert_called_once()
            lease.return_value.__exit__.assert_not_called()
            return {"exit_code": 0}
        self.boundary.execute_operator_approved_job.side_effect = execute
        result = dispatch_operator(
            self.boundary, self.request, self.verifier,
            "/etc/hermes-broker/signing.key",
            "/run/hermes-broker/fenced-candidate.sock")
        self.assertEqual(result, {"exit_code": 0})
        self.boundary.approve_operator_request.assert_called_once()
        self.boundary.execute_operator_approved_job.assert_called_once_with(
            "approval", "task", "noop", "worker", "lease",
            "/etc/hermes-broker/signing.key",
            "/run/hermes-broker/fenced-candidate.sock")
        lease.return_value.__exit__.assert_called_once()

    @patch("agency.operator_control.os.path.lexists", return_value=False)
    @patch("agency.operator_control.operator_admission_lease")
    def test_candidate_wrong_key_denied_before_grant(self, _lease, _freeze):
        with self.assertRaises(PermissionError):
            dispatch_operator(self.boundary, self.request, self.verifier,
                              "/tmp/untrusted.key",
                              "/run/hermes-broker/fenced-candidate.sock")
        self.boundary.approve_operator_request.assert_not_called()
        self.boundary.execute_operator_approved_job.assert_not_called()

    @patch("agency.operator_control.os.path.lexists", return_value=True)
    @patch("agency.operator_control.operator_admission_lease")
    def test_freeze_denies_before_approval(self, _lease, _freeze):
        with self.assertRaises(PermissionError):
            dispatch_operator(self.boundary, self.request, self.verifier,
                              "/etc/hermes-broker/signing.key",
                              "/run/hermes-broker/fenced-candidate.sock")
        self.boundary.approve_operator_request.assert_not_called()
        self.boundary.execute_operator_approved_job.assert_not_called()

    @patch("agency.operator_control.os.path.lexists", return_value=False)
    @patch("agency.operator_control.operator_admission_lease")
    def test_legacy_endpoint_unchanged(self, lease, _freeze):
        dispatch_operator(self.boundary, self.request, self.verifier,
                          "/etc/hermes-broker/signing.key",
                          "/run/hermes-broker/broker.sock")
        self.boundary.execute_operator_approved_job.assert_called_once_with(
            "approval", "task", "noop", "worker", "lease",
            "/etc/hermes-broker/signing.key",
            "/run/hermes-broker/broker.sock")
        lease.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
