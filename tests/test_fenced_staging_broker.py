"""Staging broker composition regressions; no real systemd or production access."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from agency.fenced_staging_broker import staging_broker_job, unit_for_grant


@unittest.skipUnless(os.geteuid() == 0, "Root-only staging journal tests")
class StagingBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.chmod(self.tmp.name, 0o700)
        self.journal = os.path.join(self.tmp.name, "owned.sqlite")
        with sqlite3.connect(self.journal) as db:
            db.execute("CREATE TABLE owned_units(unit TEXT PRIMARY KEY, state TEXT NOT NULL)")
        os.chmod(self.journal, 0o600)
        self.grant_id = "a" * 64
        self.grant = {"claims": {"id": self.grant_id, "job": "noop"}}
        self.unit = unit_for_grant(self.grant_id)

    def state(self):
        with sqlite3.connect(self.journal) as db:
            return db.execute("SELECT unit,state FROM owned_units").fetchall()

    def test_full_composition_order(self):
        observed = []
        def ipc(conn, grant, execute):
            observed.append("trusted_lock")
            return execute("noop")
        def supervised(job, gid, conn, runner):
            observed.append("supervisor")
            self.assertEqual(self.state(), [(self.unit, "pending")])
            return runner(job, conn, self.unit)
        def runner(job, conn, unit):
            observed.append("runner")
            self.assertEqual(unit, self.unit)
            return {"exit_code": 0}
        def stop(unit):
            observed.append("stop")
            self.assertEqual(unit, self.unit)
            return True
        with patch("agency.fenced_staging_broker.verify_broker_grant",
                   return_value=self.grant["claims"]), patch(
                   "agency.fenced_staging_broker.broker_fenced_job", side_effect=ipc), patch(
                   "agency.fenced_staging_broker.supervised_fenced_unit", side_effect=supervised), patch(
                   "agency.fenced_staging_broker.stop_and_verify_unit", side_effect=stop):
            self.assertEqual(staging_broker_job(
                object(), self.grant, b"k" * 32, self.journal, runner=runner),
                {"exit_code": 0})
        self.assertEqual(observed, ["trusted_lock", "supervisor", "runner", "stop"])
        self.assertEqual(self.state(), [(self.unit, "verified")])

    def test_failure_leaves_pending_and_blocks_next_launch(self):
        with patch("agency.fenced_staging_broker.verify_broker_grant",
                   return_value=self.grant["claims"]), patch(
                   "agency.fenced_staging_broker.broker_fenced_job",
                   side_effect=RuntimeError("injected")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                staging_broker_job(object(), self.grant, b"k" * 32,
                                   self.journal, runner=lambda *args: None)
        self.assertEqual(self.state(), [(self.unit, "pending")])
        with patch("agency.fenced_staging_broker.verify_broker_grant",
                   return_value={"id": "b" * 64, "job": "noop"}):
            with self.assertRaises(PermissionError):
                staging_broker_job(object(), self.grant, b"k" * 32,
                                   self.journal, runner=lambda *args: None)

    def test_invalid_grant_id(self):
        for value in ("", "G" * 64, "a" * 63, None):
            with self.assertRaises(PermissionError):
                unit_for_grant(value)


if __name__ == "__main__":
    unittest.main()
