"""Regression tests for cooperative operator admission freeze.

This marker is not an exclusive cutover lock; tests cover only rejection.
"""
import contextlib
import unittest
from unittest.mock import patch

from agency.operator_control import dispatch_operator


class OperatorFreezeTests(unittest.TestCase):
    def test_frozen_operator_rejects_before_approval(self):
        class Boundary:
            def approve_operator_request(self, *args):
                raise AssertionError("approval must not run")
            def execute_operator_approved_job(self, *args):
                raise AssertionError("execution must not run")

        request = {"action": "approve_and_execute", "approval_id": "a",
                   "operator_secret_hex": "00" * 32, "task_id": "t",
                   "job": "j", "worker_credential": "c", "lease_token": "l"}
        with patch("agency.operator_control.operator_admission_lease", return_value=contextlib.nullcontext()), patch("agency.operator_control.os.path.lexists", return_value=True):
            with self.assertRaisesRegex(PermissionError, "frozen"):
                dispatch_operator(Boundary(), request, ("operator", b"s", b"v"),
                                  "/unused/key", "/unused/socket")


if __name__ == "__main__":
    unittest.main()
