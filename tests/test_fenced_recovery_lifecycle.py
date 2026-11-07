"""Isolated lifecycle CLI tests; no systemd unit changes."""
import unittest
from unittest.mock import patch

from agency.fenced_unit_recovery import main


class RecoveryLifecycleCLITests(unittest.TestCase):
    @patch("agency.fenced_unit_recovery.recover_fenced_units", return_value=())
    def test_explicit_broker_stopped_gate(self, recovery):
        self.assertEqual(main(["--broker-stopped"]), 0)
        recovery.assert_called_once_with(broker_stopped=True)

    @patch("agency.fenced_unit_recovery.recover_fenced_units")
    def test_missing_gate_denied(self, recovery):
        with self.assertRaises(SystemExit) as raised:
            main([])
        self.assertNotEqual(raised.exception.code, 0)
        recovery.assert_not_called()

    @patch("agency.fenced_unit_recovery.recover_fenced_units",
           side_effect=PermissionError("unit remains active"))
    def test_recovery_failure_blocks_start(self, recovery):
        with self.assertRaises(PermissionError):
            main(["--broker-stopped"])


if __name__ == "__main__":
    unittest.main()
