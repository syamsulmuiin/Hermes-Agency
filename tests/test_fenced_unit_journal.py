"""Isolated durable ownership tests; no real systemd or production files."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from agency.fenced_unit_journal import register_before_launch, recover_owned_units
from agency.fenced_systemd_supervisor import supervised_fenced_unit

UNIT = "hermes-fenced-" + "a" * 32 + ".service"


class DurableFencedUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "owned.sqlite")
        self.uid = os.geteuid()
        self.patcher = patch("agency.fenced_unit_journal._verify_store")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_persists_before_launch_and_recovers(self):
        def runner(job, fence, unit):
            with sqlite3.connect(self.path) as db:
                self.assertEqual(db.execute(
                    "SELECT state FROM owned_units WHERE unit=?", (unit,)
                ).fetchone(), ("pending",))
            return {"exit_code": 0}
        with patch("agency.fenced_systemd_supervisor.stop_and_verify_unit"):
            supervised_fenced_unit(
                "noop", "a" * 64, None, runner, journal_path=self.path)
        recovered = []
        self.assertEqual(len(recover_owned_units(
            self.path, stop_unit=recovered.append)), 1)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recover_owned_units(self.path, stop_unit=recovered.append), ())

    def test_crash_before_launch_leaves_pending_record(self):
        register_before_launch(self.path, UNIT)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT state FROM owned_units WHERE unit=?", (UNIT,)
            ).fetchone(), ("pending",))
        self.assertEqual(recover_owned_units(
            self.path, stop_unit=lambda unit: None), (UNIT,))

    def test_failed_recovery_keeps_pending(self):
        register_before_launch(self.path, UNIT)
        with self.assertRaises(PermissionError):
            recover_owned_units(self.path, stop_unit=lambda unit:
                                (_ for _ in ()).throw(PermissionError("active")))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT state FROM owned_units WHERE unit=?", (UNIT,)
            ).fetchone(), ("pending",))

    def test_rejects_invalid_unit(self):
        with self.assertRaises(PermissionError):
            register_before_launch(self.path, "unrelated.service")


if __name__ == "__main__":
    unittest.main()
