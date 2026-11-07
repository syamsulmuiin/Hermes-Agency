"""Real operator decision -> trusted grant integration regression tests.

Uses a real SQLite approval and scrypt authentication, but intercepts broker
transport. This is NOT a live systemd or cross-UID acceptance test.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.broker_grants import verify_broker_grant
from agency.operator_auth import LocalOperatorGate
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.trusted_broker_adapter import execute_approved_job


class OperatorGrantIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SecureAgencyStore(Path(self.temp.name) / "trusted.sqlite")
        self.service = TrustedApprovalService(self.store, b"t" * 32)
        self.task = self.store.create_task("Operator approved job", "developer")
        self.approval = self.store.request_approval(
            self.task, "execute_shell", {"job": "noop"}, "developer")
        self.lease = self.store.claim(self.task, "staging-worker")
        self.worker = self.service.issue_credential("staging-worker", "worker")
        self.secret = b"isolated-test-operator-secret"
        salt, verifier = LocalOperatorGate.provision(self.secret)
        self.gate = LocalOperatorGate(self.service, "staging-operator", salt, verifier)
        self.key = b"b" * 64

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def submit(self, job="noop", worker=None, lease=None):
        captured = []
        def transport(socket_path, envelope):
            captured.append((socket_path, envelope))
            return {"exit_code": 0}
        with patch("agency.trusted_broker_adapter._trusted_key", return_value=self.key), \
             patch("agency.trusted_broker_adapter.submit_signed_grant",
                   side_effect=transport):
            response = execute_approved_job(
                self.service, self.approval, self.task, job,
                self.worker if worker is None else worker,
                self.lease if lease is None else lease,
                "/isolated/key", "/isolated/socket")
        return response, captured

    def test_real_operator_auth_approval_grant_and_replay_denial(self):
        with self.assertRaises(PermissionError):
            self.gate.authenticate(b"incorrect-operator-secret")
        with self.assertRaises(PermissionError):
            self.submit()
        self.service.decide(self.approval, self.gate.authenticate(self.secret), True)
        response, captured = self.submit()
        self.assertEqual(response["exit_code"], 0)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][0], "/isolated/socket")
        claims = verify_broker_grant(captured[0][1], self.key)
        self.assertEqual(claims["approval"], self.approval)
        self.assertEqual(claims["task"], self.task)
        self.assertEqual(claims["worker"], "staging-worker")
        self.assertEqual(claims["job"], "noop")
        self.assertEqual(claims["lease_generation"], 1)
        with self.assertRaises(PermissionError):
            self.submit()
        self.assertEqual(self.store.db.execute(
            "SELECT status FROM approvals WHERE id=?", (self.approval,)
        ).fetchone()[0], "consumed")

    def test_denial_never_submits(self):
        self.service.decide(self.approval, self.gate.authenticate(self.secret), False)
        with self.assertRaises(PermissionError):
            self.submit()

    def test_wrong_worker_and_lease_never_submit(self):
        self.service.decide(self.approval, self.gate.authenticate(self.secret), True)
        with self.assertRaises(PermissionError):
            self.submit(worker=self.service.issue_credential("intruder", "worker"))
        with self.assertRaises(PermissionError):
            self.submit(lease="invalid-lease")
        self.assertEqual(self.store.db.execute(
            "SELECT status FROM approvals WHERE id=?", (self.approval,)
        ).fetchone()[0], "approved")

    def test_unallowlisted_job_never_submits(self):
        self.service.decide(self.approval, self.gate.authenticate(self.secret), True)
        with self.assertRaises(PermissionError):
            self.submit(job="arbitrary-shell-command")


if __name__ == "__main__":
    unittest.main()
