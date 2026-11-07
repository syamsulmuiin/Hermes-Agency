"""Isolated broker ledger/IPC integration tests; fake fixed job only."""
import os
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.systemd_broker import execute_fenced_signed_grant
from agency.trusted_lease_ipc import serve_fence_connection
from tests.test_trusted_lease_ipc import TrustedLeaseIPCTests


class BrokerFencedLedgerTests(unittest.TestCase):
    setUp = TrustedLeaseIPCTests.setUp
    tearDown = TrustedLeaseIPCTests.tearDown
    def test_atomic_consumption_replay_and_fence(self):
        ledger = str(Path(self.tmp.name) / "ledger.sqlite")
        sqlite3.connect(ledger).close()
        path = str(Path(self.tmp.name) / "fence.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path)
        listener.listen(3)
        errors = []
        def server():
            try:
                for _ in range(2):
                    conn, _ = listener.accept()
                    with conn:
                        try:
                            serve_fence_connection(
                                conn, self.dbpath, self.key,
                                root_uid=os.getuid(), now=100)
                        except (PermissionError, OSError) as exc:
                            errors.append(exc)
            finally:
                listener.close()
        thread = threading.Thread(target=server)
        thread.start()
        executions = []
        def job(name):
            executions.append(name)
            with sqlite3.connect(self.dbpath, timeout=0.05) as competitor:
                with self.assertRaises(sqlite3.OperationalError):
                    competitor.execute(
                        "DELETE FROM task_leases WHERE task_id=?", (self.task,))
            return {"exit_code": 0}
        try:
            with patch("agency.systemd_broker.verify_private_ledger"):
                result = execute_fenced_signed_grant(
                    ledger, self.grant, self.key, path, executor=job, now=100)
                self.assertEqual(result["exit_code"], 0)
                with self.assertRaises(PermissionError):
                    execute_fenced_signed_grant(
                        ledger, self.grant, self.key, path,
                        executor=job, now=100)
            self.assertEqual(executions, ["noop"])
            with sqlite3.connect(ledger) as db:
                rows = db.execute(
                    "SELECT grant_id,status FROM signed_grant_consumptions").fetchall()
            self.assertEqual(rows, [(self.grant["claims"]["id"], "completed")])
        finally:
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
