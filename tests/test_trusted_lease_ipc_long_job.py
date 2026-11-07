"""Long-running IPC regression: lease lock must outlive handshake timeout.

Isolated socketpair and fake job; no production services or real systemd jobs.
"""
import os
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from agency.broker_grants import issue_broker_grant
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.trusted_lease_ipc import broker_fenced_job, serve_fence_connection


class LongRunningFenceTests(unittest.TestCase):
    def test_job_longer_than_ten_seconds_keeps_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "trusted.sqlite")
            store = SecureAgencyStore(path, clock=lambda: 100.0)
            try:
                auth = TrustedApprovalService(store, b"s" * 32, clock=lambda: 100.0)
                task = store.create_task("Long job", "developer")
                token = store.claim(task, "worker", ttl=60)
                worker = auth.issue_credential("worker", "worker")
                approval = store.request_approval(
                    task, "execute_shell", {"job": "noop"}, "developer")
                auth.decide(approval, auth.issue_credential("reviewer", "approver"), True)
                key = b"k" * 32
                grant = issue_broker_grant(
                    auth, approval, task, "noop", worker, token, key)
                a, b = socket.socketpair()
                errors = []

                def trusted():
                    with a:
                        try:
                            serve_fence_connection(
                                a, path, key, root_uid=os.getuid(), now=100)
                        except Exception as exc:
                            errors.append(exc)

                thread = threading.Thread(target=trusted)
                thread.start()
                try:
                    with b:
                        def job(name):
                            self.assertEqual(name, "noop")
                            # The original protocol timed out after 10 seconds.
                            time.sleep(10.25)
                            with sqlite3.connect(path, timeout=0.05) as other:
                                with self.assertRaises(sqlite3.OperationalError):
                                    other.execute(
                                        "DELETE FROM task_leases WHERE task_id=?",
                                        (task,))
                            return {"exit_code": 0}
                        self.assertEqual(
                            broker_fenced_job(b, grant, job)["exit_code"], 0)
                finally:
                    thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertFalse(errors, repr(errors))
                with sqlite3.connect(path, timeout=0.2) as other:
                    other.execute(
                        "DELETE FROM task_leases WHERE task_id=?", (task,))
                    other.commit()
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
