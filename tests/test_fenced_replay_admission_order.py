"""Regression: replay admission cannot mutate the ownership journal."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from agency.fenced_staging_serialization import staging_launch
from agency.fenced_unit_journal import _connect


class ReplayAdmissionTests(unittest.TestCase):
    def test_rejected_admission_does_not_register_unit(self):
        with tempfile.TemporaryDirectory(prefix="hermes-replay-test-") as folder:
            journal = os.path.join(folder, "owned.sqlite")
            with _connect(journal):
                pass
            unit = "hermes-fenced-" + "a" * 32 + ".service"
            with patch("agency.fenced_staging_serialization.os.geteuid", return_value=0):
                with self.assertRaisesRegex(PermissionError, "Grant replay denied"):
                    staging_launch(journal, unit, lambda: self.fail("Launched replay"),
                                   admit=lambda: (_ for _ in ()).throw(
                                       PermissionError("Grant replay denied")))
            with sqlite3.connect(journal) as db:
                self.assertEqual(db.execute(
                    "SELECT COUNT(*) FROM owned_units").fetchone()[0], 0)

    def test_admission_precedes_registration(self):
        with tempfile.TemporaryDirectory(prefix="hermes-replay-test-") as folder:
            journal = os.path.join(folder, "owned.sqlite")
            with _connect(journal):
                pass
            unit = "hermes-fenced-" + "b" * 32 + ".service"
            sequence = []
            def admit():
                sequence.append("admit")
                with sqlite3.connect(journal) as db:
                    self.assertEqual(db.execute(
                        "SELECT COUNT(*) FROM owned_units").fetchone()[0], 0)
            def launch():
                sequence.append("launch")
                with sqlite3.connect(journal) as db:
                    self.assertEqual(db.execute(
                        "SELECT state FROM owned_units WHERE unit=?",
                        (unit,)).fetchone(), ("pending",))
            with patch("agency.fenced_staging_serialization.os.geteuid", return_value=0):
                staging_launch(journal, unit, launch, admit=admit)
            self.assertEqual(sequence, ["admit", "launch"])


if __name__ == "__main__":
    unittest.main()
