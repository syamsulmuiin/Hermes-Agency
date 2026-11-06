"""Positive authenticated workflow integration tests with trusted-only issuance.

This is an isolated temporary SQLite test, not a live-service test.
Credentials are minted only by the trusted approval service; no signing key
is sent to the worker-facing execution boundary.
"""
import os
import tempfile
import unittest

from agency.security import SecureAgencyStore
from agency.orchestrator import WorkflowCoordinator
from agency.portable_runtime import PortableAgentRuntime
from agency.trusted import TrustedApprovalService
from agency.trusted_execution import TrustedAgentExecution


RESULT = {"completed": ["verified"], "output": [], "notes": [], "blockers": []}


class PositiveTrustedWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "test.db")
        self.key = os.urandom(64)
        self.open_store()

    def open_store(self):
        self.store = SecureAgencyStore(self.path)
        self.coordinator = WorkflowCoordinator(self.store)
        self.runtime = PortableAgentRuntime(self.coordinator)
        self.issuer = TrustedApprovalService(self.store, self.key)
        self.boundary = TrustedAgentExecution(self.runtime, self.issuer)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_trusted_credential_advances_and_survives_reopen(self):
        task = self.runtime.start("Isolated integration test")
        credential = self.issuer.issue_credential("ceo", "worker", ttl=60)
        state = self.boundary.submit_stage(task, "ceo", RESULT, credential)
        self.assertEqual(state["stage"], 1)
        self.assertEqual(state["owner"], "pm")
        self.store.close()
        self.open_store()
        state = self.runtime.snapshot(task)
        self.assertEqual((state["stage"], state["owner"]), (1, "pm"))
        credential = self.issuer.issue_credential("pm", "worker", ttl=60)
        state = self.boundary.submit_stage(task, "pm", RESULT, credential)
        self.assertEqual((state["stage"], state["owner"]), (2, "researcher"))

    def test_wrong_identity_and_forgery_do_not_advance(self):
        task = self.runtime.start("Denied integration test")
        credential = self.issuer.issue_credential("pm", "worker", ttl=60)
        with self.assertRaises(PermissionError):
            self.boundary.submit_stage(task, "ceo", RESULT, credential)
        with self.assertRaises(PermissionError):
            self.boundary.submit_stage(task, "ceo", RESULT, "invalid.credential")
        state = self.runtime.snapshot(task)
        self.assertEqual((state["stage"], state["owner"]), (0, "ceo"))
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) FROM handoffs WHERE task_id=?", (task,)).fetchone()[0],
            0,
        )

    def test_approver_role_cannot_submit_stage(self):
        task = self.runtime.start("Role isolation test")
        credential = self.issuer.issue_credential("ceo", "approver", ttl=60)
        with self.assertRaises(PermissionError):
            self.boundary.submit_stage(task, "ceo", RESULT, credential)
        self.assertEqual(self.runtime.snapshot(task)["stage"], 0)


if __name__ == "__main__":
    unittest.main()
