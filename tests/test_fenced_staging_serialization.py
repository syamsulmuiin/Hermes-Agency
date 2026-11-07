"""Regression tests for staging journal serialization; no systemd execution."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from agency.fenced_staging_serialization import staging_launch, staging_recover


@unittest.skipUnless(os.geteuid() == 0, "Root-only journal integration tests")
class StagingSerializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.journal = os.path.join(self.tmp.name, "owned.sqlite")
        with sqlite3.connect(self.journal) as db:
            db.execute("CREATE TABLE owned_units(unit TEXT PRIMARY KEY, state TEXT NOT NULL)")
        os.chmod(self.tmp.name, 0o700)
        os.chmod(self.journal, 0o600)

    def test_register_before_launch_and_pending_gate(self):
        unit = "hermes-fenced-" + "a" * 32 + ".service"
        with patch("agency.fenced_staging_serialization.os.geteuid", return_value=0):
            with patch("agency.fenced_startup_gate.os.geteuid", return_value=0):
                def launch():
                    with sqlite3.connect(self.journal) as db:
                        self.assertEqual(db.execute(
                            "SELECT state FROM owned_units WHERE unit=?", (unit,)
                        ).fetchone(), ("pending",))
                    return "launched"
                self.assertEqual(staging_launch(self.journal, unit, launch), "launched")
                with self.assertRaises(PermissionError):
                    staging_launch(self.journal, "hermes-fenced-" + "b" * 32 + ".service", launch)
                self.assertEqual(staging_recover(self.journal, stop_unit=lambda u: True), (unit,))
                self.assertEqual(staging_launch(
                    self.journal, "hermes-fenced-" + "c" * 32 + ".service", lambda: "launched"), "launched")

    def test_reject_non_root(self):
        with patch("agency.fenced_staging_serialization.os.geteuid", return_value=1000):
            with self.assertRaises(PermissionError):
                staging_recover(self.journal, stop_unit=lambda u: True)

    def test_launch_failure_leaves_pending(self):
        unit = "hermes-fenced-" + "d" * 32 + ".service"
        with patch("agency.fenced_staging_serialization.os.geteuid", return_value=0):
            with patch("agency.fenced_startup_gate.os.geteuid", return_value=0):
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    staging_launch(self.journal, unit, lambda: (_ for _ in ()).throw(RuntimeError("injected")))
                with sqlite3.connect(self.journal) as db:
                    self.assertEqual(db.execute("SELECT state FROM owned_units").fetchone(), ("pending",))


if __name__ == "__main__":
    unittest.main()
