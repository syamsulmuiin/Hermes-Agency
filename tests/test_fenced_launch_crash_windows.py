"""Fault-window regression for the isolated fenced launch journal.

No systemd commands, production sockets, or production databases are used.
"""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from agency.fenced_staging_serialization import staging_launch, staging_recover
from agency.fenced_startup_gate import require_recovered
from agency.fenced_unit_journal import _connect


class FencedLaunchCrashWindows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hermes-fenced-window-")
        self.addCleanup(self.tmp.cleanup)
        self.journal = os.path.join(self.tmp.name, "owned.sqlite")
        with _connect(self.journal):
            pass
        self.unit = "hermes-fenced-" + "c" * 32 + ".service"
        self.root = patch("agency.fenced_staging_serialization.os.geteuid", return_value=0)
        self.root.start()
        self.addCleanup(self.root.stop)
        self.gate_root = patch("agency.fenced_startup_gate.os.geteuid", return_value=0)
        self.gate_root.start()
        self.addCleanup(self.gate_root.stop)

    def state(self):
        with sqlite3.connect(self.journal) as db:
            return db.execute("SELECT unit,state FROM owned_units").fetchall()

    def test_crash_before_admission_leaves_no_unit(self):
        with self.assertRaisesRegex(RuntimeError, "before admission"):
            staging_launch(self.journal, self.unit, lambda: None,
                           admit=lambda: (_ for _ in ()).throw(
                               RuntimeError("before admission")))
        self.assertEqual(self.state(), [])
        self.assertTrue(require_recovered(self.journal))

    def test_crash_after_admission_before_registration_is_fail_closed(self):
        admitted = []
        def admit():
            admitted.append(True)
            raise RuntimeError("after admission")
        with self.assertRaisesRegex(RuntimeError, "after admission"):
            staging_launch(self.journal, self.unit, lambda: None, admit=admit)
        self.assertEqual(admitted, [True])
        self.assertEqual(self.state(), [])
        # The ledger admission is independently durable; a caller must not retry
        # the same consumed grant after an interrupted launch.
        self.assertTrue(require_recovered(self.journal))

    def test_crash_after_registration_preserves_pending_until_verified_stop(self):
        with self.assertRaisesRegex(RuntimeError, "after registration"):
            staging_launch(self.journal, self.unit,
                           lambda: (_ for _ in ()).throw(
                               RuntimeError("after registration")))
        self.assertEqual(self.state(), [(self.unit, "pending")])
        with self.assertRaises(PermissionError):
            require_recovered(self.journal)
        with self.assertRaises(PermissionError):
            staging_recover(self.journal, stop_unit=lambda _: (
                _ for _ in ()).throw(PermissionError("stop failed")))
        self.assertEqual(self.state(), [(self.unit, "pending")])
        with self.assertRaises(PermissionError):
            staging_launch(self.journal,
                           "hermes-fenced-" + "d" * 32 + ".service",
                           lambda: None)
        stopped = []
        self.assertEqual(staging_recover(
            self.journal, stop_unit=lambda unit: stopped.append(unit)),
            (self.unit,))
        self.assertEqual(stopped, [self.unit])
        self.assertEqual(self.state(), [(self.unit, "verified")])
        self.assertTrue(require_recovered(self.journal))


if __name__ == "__main__":
    unittest.main()
