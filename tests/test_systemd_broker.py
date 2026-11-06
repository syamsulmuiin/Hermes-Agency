import sqlite3
import tempfile
import unittest
from pathlib import Path

from agency.systemd_broker import execute_approved


class SystemdBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "broker.sqlite")
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE approvals (id TEXT PRIMARY KEY, job TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)")
            conn.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY, approval_id TEXT, job TEXT, status TEXT, timestamp INTEGER)")
            conn.execute("INSERT INTO approvals(id,job) VALUES (?,?)", ("a" * 32, "noop"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_approved_job_executes_once(self):
        calls = []
        result = execute_approved(self.db, "a" * 32, "noop", executor=lambda job: calls.append(job) or {"ok": True})
        self.assertTrue(result["ok"])
        self.assertEqual(calls, ["noop"])
        with self.assertRaises(PermissionError):
            execute_approved(self.db, "a" * 32, "noop", executor=lambda job: calls.append(job))
        self.assertEqual(calls, ["noop"])

    def test_arbitrary_job_denied(self):
        with self.assertRaises(PermissionError):
            execute_approved(self.db, "a" * 32, "/bin/sh", executor=lambda job: None)

    def test_unknown_approval_denied(self):
        with self.assertRaises(PermissionError):
            execute_approved(self.db, "b" * 32, "noop", executor=lambda job: None)

    def test_failure_consumes_approval_and_audits(self):
        def fail(job):
            raise RuntimeError("simulated")
        with self.assertRaises(RuntimeError):
            execute_approved(self.db, "a" * 32, "noop", executor=fail)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT consumed FROM approvals").fetchone()[0], 1)
            self.assertEqual([r[0] for r in conn.execute("SELECT status FROM audit ORDER BY id")], ["started", "failed"])

    def test_job_mismatch_denied(self):
        with self.assertRaises(PermissionError):
            execute_approved(self.db, "a" * 32, "identity", executor=lambda job: None)


if __name__ == "__main__":
    unittest.main()
