"""Concurrency regression for cooperative staging recovery and launch.

No systemd unit is launched; verifies that a second admission cannot pass
while the first launch holds the journal lock and pending gate.
"""
import os
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from agency.fenced_staging_serialization import staging_launch, staging_recover


@unittest.skipUnless(os.geteuid() == 0, "Root-only staging journal test")
class StagingConcurrencyTests(unittest.TestCase):
    def test_pending_launch_blocks_concurrent_recovery_until_release(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            journal = os.path.join(folder, "owned.sqlite")
            with sqlite3.connect(journal) as db:
                db.execute("CREATE TABLE owned_units(unit TEXT PRIMARY KEY, state TEXT NOT NULL)")
            os.chmod(journal, 0o600)
            unit = "hermes-fenced-" + "a" * 32 + ".service"
            entered = threading.Event()
            release = threading.Event()
            recovered = threading.Event()
            errors = []

            def launch():
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("Launch release timeout")

            def launching():
                try:
                    staging_launch(journal, unit, launch)
                except BaseException as exc:
                    errors.append(exc)

            def recovering():
                try:
                    staging_recover(journal, stop_unit=lambda _: recovered.set())
                except BaseException as exc:
                    errors.append(exc)

            t1 = threading.Thread(target=launching)
            t2 = threading.Thread(target=recovering)
            t1.start()
            try:
                self.assertTrue(entered.wait(5))
                t2.start()
                self.assertFalse(recovered.wait(.2),
                                 "Recovery ran before launch lock release")
            finally:
                release.set()
                t1.join(5)
                if t2.ident is not None:
                    t2.join(5)
            self.assertFalse(t1.is_alive())
            self.assertFalse(t2.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(recovered.is_set())
            with sqlite3.connect(journal) as db:
                self.assertEqual(db.execute(
                    "SELECT state FROM owned_units WHERE unit=?", (unit,)
                ).fetchone(), ("verified",))


if __name__ == "__main__":
    unittest.main()
