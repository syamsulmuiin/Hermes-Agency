"""Mocked startup-gate tests; no real broker or systemd changes."""
import unittest
from unittest.mock import patch

from agency.fenced_unit_recovery import main


class DurableRecoveryGateTests(unittest.TestCase):
    @patch("agency.fenced_unit_recovery.os.path.isfile", return_value=True)
    @patch("agency.fenced_unit_journal.recover_owned_units", return_value=("hermes-fenced-" + "a"*32 + ".service",))
    @patch("agency.fenced_unit_recovery.recover_fenced_units", return_value=())
    def test_journal_recovered_before_discovery(self, scan, journal, exists):
        self.assertEqual(main(["--broker-stopped", "--journal", "/root/owned.sqlite"]), 0)
        journal.assert_called_once_with("/root/owned.sqlite")
        scan.assert_called_once_with(broker_stopped=True)

    @patch("agency.fenced_unit_recovery.os.path.isfile", return_value=True)
    @patch("agency.fenced_unit_journal.recover_owned_units",
           side_effect=PermissionError("unit still active"))
    @patch("agency.fenced_unit_recovery.recover_fenced_units")
    def test_pending_failure_prevents_scan_and_start(self, scan, journal, exists):
        with self.assertRaises(PermissionError):
            main(["--broker-stopped", "--journal", "/root/owned.sqlite"])
        scan.assert_not_called()

    @patch("agency.fenced_unit_recovery.os.path.isfile", return_value=False)
    @patch("agency.fenced_unit_recovery.recover_fenced_units")
    def test_missing_journal_denied(self, scan, exists):
        with self.assertRaises(PermissionError):
            main(["--broker-stopped", "--journal", "/root/missing.sqlite"])
        scan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
