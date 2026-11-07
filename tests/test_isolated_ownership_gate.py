"""Isolated ownership journal and startup-gate safety regression tests.

Uses a temporary SQLite journal only. Never invokes systemctl or real recovery.
"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency import fenced_startup_gate as gate
from agency import fenced_unit_journal as journal


class IsolatedOwnershipGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hermes-owned-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "owned.sqlite")
        self.root = patch.object(gate.os, "geteuid", return_value=0)
        self.root.start()
        self.addCleanup(self.root.stop)
        self.verify_gate = patch.object(gate, "_verify_store", side_effect=self._check_store)
        self.verify_gate.start()
        self.addCleanup(self.verify_gate.stop)
        self.verify_journal = patch.object(journal, "_verify_store", side_effect=self._check_store)
        self.verify_journal.start()
        self.addCleanup(self.verify_journal.stop)

    def _check_store(self, path):
        self.assertEqual(path, self.path)
        self.assertFalse(os.path.islink(path))

    def _create(self):
        with journal._connect(self.path):
            pass

    def test_missing_journal_denied_without_creation(self):
        with self.assertRaises(PermissionError):
            gate.require_recovered(self.path)
        self.assertFalse(os.path.exists(self.path))

    def test_corrupt_journal_denied_and_bytes_preserved(self):
        data = b"not-a-sqlite-database"
        Path(self.path).write_bytes(data)
        with self.assertRaises(sqlite3.DatabaseError):
            gate.require_recovered(self.path)
        self.assertEqual(Path(self.path).read_bytes(), data)

    def test_empty_valid_journal_allowed(self):
        self._create()
        self.assertTrue(gate.require_recovered(self.path))

    def test_pending_denied_and_record_unchanged(self):
        self._create()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO owned_units VALUES (?, ?)", ("hermes-fenced-test.service", "pending"))
        with self.assertRaises(PermissionError):
            gate.require_recovered(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT state FROM owned_units").fetchone()[0], "pending")

    def test_verified_record_allowed_and_retained(self):
        self._create()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO owned_units VALUES (?, ?)", ("hermes-fenced-test.service", "verified"))
        self.assertTrue(gate.require_recovered(self.path))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM owned_units").fetchone()[0], 1)

    def test_failed_recovery_keeps_pending_ownership(self):
        self._create()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO owned_units VALUES (?, ?)", ("hermes-fenced-test.service", "pending"))
        def failed_stop(unit):
            raise RuntimeError("simulated stop verification failure")
        with self.assertRaises(RuntimeError):
            journal.recover_owned_units(self.path, stop_unit=failed_stop)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT state FROM owned_units").fetchone()[0], "pending")
        with self.assertRaises(PermissionError):
            gate.require_recovered(self.path)


if __name__ == "__main__":
    unittest.main()
