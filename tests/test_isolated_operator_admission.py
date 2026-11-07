"""Isolated operator admission integration tests using a real flock inode.

No production paths, service changes, broker credentials, or systemd operations.
"""
import fcntl
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from agency.operator_control import dispatch_operator


class IsolatedOperatorAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hermes-operator-isolated-")
        self.addCleanup(self.tmp.cleanup)
        self.lock = os.path.join(self.tmp.name, "admission.lock")
        with open(self.lock, "xb"):
            pass
        self.request = {
            "action": "approve_and_execute", "approval_id": "a",
            "operator_secret_hex": "a" * 64, "task_id": "t",
            "job": "noop", "worker_credential": "w", "lease_token": "l",
        }
        self.verifier = ("operator", b"salt", b"proof")
        self.boundary = Mock()

    @patch("agency.operator_control.os.path.lexists", return_value=False)
    def test_approval_and_execution_hold_same_real_lock(self, _freeze):
        # The production admission lock requires root ownership and exact 0640.
        os.chmod(self.lock, 0o640)
        def check_exclusive_blocked(*_args):
            contender = os.open(self.lock, os.O_RDONLY)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(contender)
        self.boundary.approve_operator_request.side_effect = check_exclusive_blocked
        self.boundary.execute_operator_approved_job.side_effect = check_exclusive_blocked
        with patch("agency.operator_control.os.geteuid", return_value=1000):
            dispatch_operator(
                self.boundary, self.request, self.verifier,
                "/etc/hermes-broker/signing.key",
                "/run/hermes-broker/fenced-candidate.sock",
                admission_lock=self.lock)
        self.boundary.approve_operator_request.assert_called_once()
        self.boundary.execute_operator_approved_job.assert_called_once()

    @patch("agency.operator_control.os.path.lexists", return_value=False)
    def test_exclusive_maintenance_drain_denies_before_approval(self, _freeze):
        os.chmod(self.lock, 0o640)
        contender = os.open(self.lock, os.O_RDONLY)
        try:
            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(PermissionError):
                dispatch_operator(
                    self.boundary, self.request, self.verifier,
                    "/etc/hermes-broker/signing.key",
                    "/run/hermes-broker/fenced-candidate.sock",
                    admission_lock=self.lock)
        finally:
            fcntl.flock(contender, fcntl.LOCK_UN)
            os.close(contender)
        self.boundary.approve_operator_request.assert_not_called()
        self.boundary.execute_operator_approved_job.assert_not_called()


if __name__ == "__main__":
    unittest.main()
