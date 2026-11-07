"""Regression tests for the trusted-owned lease lock primitive."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agency.broker_grants import issue_broker_grant
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.trusted_lease_fence import fenced_lease


class TrustedLeaseFenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "trusted.sqlite")
        self.store = SecureAgencyStore(self.path, clock=lambda: 100.0)
        self.service = TrustedApprovalService(
            self.store, b"s" * 32, clock=lambda: 100.0)
        task = self.store.create_task("Fence test", "developer")
        lease = self.store.claim(task, "worker", ttl=60)
        worker = self.service.issue_credential("worker", "worker")
        approval = self.store.request_approval(
            task, "execute_shell", {"job": "noop"}, "developer")
        reviewer = self.service.issue_credential("reviewer", "approver")
        self.service.decide(approval, reviewer, True)
        self.claims = issue_broker_grant(
            self.service, approval, task, "noop",
            worker, lease, b"k" * 32)["claims"]
        self.task = task

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_valid_lease_holds_writer_lock(self):
        with fenced_lease(self.path, self.claims, now=100, timeout=0.1):
            with sqlite3.connect(self.path, timeout=0.05) as competitor:
                with self.assertRaises(sqlite3.OperationalError):
                    competitor.execute(
                        "DELETE FROM task_leases WHERE task_id=?", (self.task,))
        with sqlite3.connect(self.path, timeout=0.2) as competitor:
            competitor.execute(
                "DELETE FROM task_leases WHERE task_id=?", (self.task,))
            competitor.commit()

    def test_revoked_lease_fails_closed(self):
        self.store.db.execute(
            "DELETE FROM task_leases WHERE task_id=?", (self.task,))
        self.store.db.commit()
        with self.assertRaises(PermissionError):
            with fenced_lease(self.path, self.claims, now=100):
                self.fail("Revoked lease admitted")

    def test_exception_releases_lock(self):
        with self.assertRaisesRegex(RuntimeError, "job failed"):
            with fenced_lease(self.path, self.claims, now=100):
                raise RuntimeError("job failed")
        with sqlite3.connect(self.path, timeout=0.2) as competitor:
            competitor.execute(
                "DELETE FROM task_leases WHERE task_id=?", (self.task,))
            competitor.commit()

    def test_invalid_path_rejected(self):
        with self.assertRaises(PermissionError):
            with fenced_lease("relative.sqlite", self.claims, now=100):
                pass

    def test_expired_lease_rejected(self):
        with self.assertRaises(PermissionError):
            with fenced_lease(self.path, self.claims, now=161):
                self.fail("Expired lease admitted")


if __name__ == "__main__":
    unittest.main()
