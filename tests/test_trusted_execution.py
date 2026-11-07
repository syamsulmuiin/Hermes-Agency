import tempfile
import unittest

from agency.orchestrator import WorkflowCoordinator
from agency.portable_runtime import PortableAgentRuntime
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.trusted_execution import TrustedAgentExecution
from agency.operator_auth import LocalOperatorGate


class TrustedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SecureAgencyStore(self.temp.name + "/agency.db")
        self.service = TrustedApprovalService(self.store, b"s" * 32)
        self.runtime = PortableAgentRuntime(WorkflowCoordinator(self.store))
        self.boundary = TrustedAgentExecution(self.runtime, self.service)
        self.task = self.runtime.start("Test trusted workflow")
        self.result = {k: [] for k in ("completed", "output", "notes", "blockers")}

    def test_valid_worker_advances_stage(self):
        token = self.service.issue_credential("ceo", "worker")
        state = self.boundary.submit_stage(self.task, "ceo", self.result, token)
        self.assertEqual(state["owner"], "pm")

    def test_wrong_identity_denied_without_mutation(self):
        token = self.service.issue_credential("pm", "worker")
        with self.assertRaises(PermissionError):
            self.boundary.submit_stage(self.task, "ceo", self.result, token)
        self.assertEqual(self.runtime.snapshot(self.task)["owner"], "ceo")

    def test_approver_role_denied(self):
        token = self.service.issue_credential("ceo", "approver")
        with self.assertRaises(PermissionError):
            self.boundary.submit_stage(self.task, "ceo", self.result, token)

    def test_bad_credential_denied(self):
        with self.assertRaises(PermissionError):
            self.boundary.submit_stage(self.task, "ceo", self.result, "invalid")

    def test_operator_secret_required_before_approval(self):
        approval = self.store.request_approval(
            self.task, "execute_shell", {"job": "noop"}, "ceo"
        )
        secret = b"test-operator-secret-with-enough-entropy"
        salt, verifier = LocalOperatorGate.provision(secret)
        with self.assertRaises(PermissionError):
            self.boundary.approve_operator_request(
                approval, b"wrong-secret-long-enough", "operator", salt, verifier
            )
        self.assertEqual(
            self.store.db.execute(
                "SELECT status FROM approvals WHERE id=?", (approval,)
            ).fetchone()[0],
            "pending",
        )
        self.boundary.approve_operator_request(
            approval, secret, "operator", salt, verifier
        )
        self.assertEqual(
            self.store.db.execute(
                "SELECT status FROM approvals WHERE id=?", (approval,)
            ).fetchone()[0],
            "approved",
        )

    def test_worker_credential_is_not_operator_authorization(self):
        approval = self.store.request_approval(
            self.task, "execute_shell", {"job": "noop"}, "ceo"
        )
        salt, verifier = LocalOperatorGate.provision(
            b"operator-secret-unused-in-worker-case"
        )
        worker = self.service.issue_credential("ceo", "worker")
        with self.assertRaises(PermissionError):
            self.boundary.approve_operator_request(
                approval, worker.encode("ascii"), "operator", salt, verifier
            )
        self.assertEqual(
            self.store.db.execute(
                "SELECT status FROM approvals WHERE id=?", (approval,)
            ).fetchone()[0],
            "pending",
        )

    def test_shared_store_required(self):
        with tempfile.TemporaryDirectory() as d:
            other = SecureAgencyStore(d + "/other.db")
            with self.assertRaises(ValueError):
                TrustedAgentExecution(self.runtime, TrustedApprovalService(other, b"k" * 32))
