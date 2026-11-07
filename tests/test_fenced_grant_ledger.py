"""Atomic fenced-grant ledger admission tests; no systemd interaction."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.fenced_grant_ledger import consume_fenced_grant, finish_fenced_grant


class FencedGrantLedgerTests(unittest.TestCase):
    def test_one_time_admission_and_verified_completion(self):
        claims = {"id": "a" * 64, "task": "t", "worker": "w",
                  "lease_generation": 1, "job": "noop", "approval": "a"}
        with tempfile.TemporaryDirectory() as directory:
            ledger = str(Path(directory) / "ledger.sqlite")
            sqlite3.connect(ledger).close()
            with patch("agency.fenced_grant_ledger.verify_private_ledger"), \
                 patch("agency.fenced_grant_ledger.verify_broker_grant",
                       return_value=claims):
                self.assertEqual(
                    consume_fenced_grant(ledger, {}, b"x" * 32), claims)
                with self.assertRaisesRegex(PermissionError, "replay"):
                    consume_fenced_grant(ledger, {}, b"x" * 32)
                finish_fenced_grant(ledger, claims["id"], verified=True)
                with self.assertRaises(PermissionError):
                    finish_fenced_grant(ledger, claims["id"], verified=True)
            with sqlite3.connect(ledger) as db:
                self.assertEqual(db.execute(
                    "SELECT status FROM signed_grant_consumptions").fetchone(),
                    ("completed",))

    def test_failed_grant_remains_consumed(self):
        claims = {"id": "b" * 64, "task": "t", "worker": "w",
                  "lease_generation": 1, "job": "noop", "approval": "a"}
        with tempfile.TemporaryDirectory() as directory:
            ledger = str(Path(directory) / "ledger.sqlite")
            sqlite3.connect(ledger).close()
            with patch("agency.fenced_grant_ledger.verify_private_ledger"), \
                 patch("agency.fenced_grant_ledger.verify_broker_grant",
                       return_value=claims):
                consume_fenced_grant(ledger, {}, b"x" * 32)
                finish_fenced_grant(ledger, claims["id"], verified=False)
                with self.assertRaisesRegex(PermissionError, "replay"):
                    consume_fenced_grant(ledger, {}, b"x" * 32)


if __name__ == "__main__":
    unittest.main()
