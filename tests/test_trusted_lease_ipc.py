"""Isolated IPC regression tests; no production socket or systemd job."""
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.broker_grants import issue_broker_grant
from agency.trusted_lease_ipc import serve_fence_connection, broker_fenced_job


class TrustedLeaseIPCTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpath = str(Path(self.tmp.name) / "trusted.sqlite")
        self.store = SecureAgencyStore(self.dbpath, clock=lambda: 100.0)
        self.auth = TrustedApprovalService(self.store, b"s" * 32,
                                           clock=lambda: 100.0)
        self.task = self.store.create_task("IPC fixture", "developer")
        token = self.store.claim(self.task, "worker", ttl=60)
        worker = self.auth.issue_credential("worker", "worker")
        approval = self.store.request_approval(
            self.task, "execute_shell", {"job": "noop"}, "developer")
        self.auth.decide(approval, self.auth.issue_credential(
            "reviewer", "approver"), True)
        self.key = b"k" * 32
        self.grant = issue_broker_grant(
            self.auth, approval, self.task, "noop", worker, token, self.key)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def run_session(self, *, disconnect=False):
        a, b = socket.socketpair()
        outcome = {}
        def server():
            with a:
                try:
                    outcome["server"] = serve_fence_connection(
                        a, self.dbpath, self.key, root_uid=__import__("os").getuid(),
                        now=100)
                except Exception as exc:
                    outcome["error"] = exc
        thread = threading.Thread(target=server)
        thread.start()
        with b:
            if disconnect:
                import json
                b.sendall((json.dumps({"grant": self.grant}) + "\n").encode())
                self.assertIn(b"locked", b.recv(4096))
            else:
                def execute(job):
                    self.assertEqual(job, "noop")
                    with sqlite3.connect(self.dbpath, timeout=0.05) as competitor:
                        with self.assertRaises(sqlite3.OperationalError):
                            competitor.execute("DELETE FROM task_leases WHERE task_id=?",
                                               (self.task,))
                    return {"exit_code": 0}
                outcome["client"] = broker_fenced_job(b, self.grant, execute)
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        return outcome

    def test_lock_held_through_job(self):
        result = self.run_session()
        self.assertEqual(result["client"]["exit_code"], 0)
        self.assertEqual(result["server"], self.grant["claims"]["id"])

    def test_disconnect_releases_lock(self):
        result = self.run_session(disconnect=True)
        self.assertIsInstance(result.get("error"), PermissionError)
        with sqlite3.connect(self.dbpath, timeout=0.2) as db:
            db.execute("DELETE FROM task_leases WHERE task_id=?", (self.task,))
            db.commit()

    def test_revoked_lease_denied_before_job(self):
        self.store.db.execute("DELETE FROM task_leases WHERE task_id=?", (self.task,))
        self.store.db.commit()
        a, b = socket.socketpair()
        errors = []
        def server():
            with a:
                try:
                    serve_fence_connection(a, self.dbpath, self.key,
                                           root_uid=__import__("os").getuid(), now=100)
                except Exception as exc:
                    errors.append(exc)
        thread = threading.Thread(target=server)
        thread.start()
        with b:
            with self.assertRaises((PermissionError, ConnectionError)):
                broker_fenced_job(b, self.grant,
                                  lambda job: self.fail("Revoked job executed"))
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertIsInstance(errors[0], PermissionError)


if __name__ == "__main__":
    unittest.main()
