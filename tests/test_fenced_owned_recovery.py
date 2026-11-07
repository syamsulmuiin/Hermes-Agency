"""Independent recovery entrypoint fail-closed behavior."""
import unittest
from unittest.mock import patch

from agency.fenced_owned_recovery import recover_owned_journal


class RecoveryEntrypointTests(unittest.TestCase):
    @patch("agency.fenced_owned_recovery.os.geteuid", return_value=1001)
    def test_non_root_denied(self, _uid):
        with self.assertRaises(PermissionError):
            recover_owned_journal("/var/lib/hermes-broker/owned-units.sqlite")

    @patch("agency.fenced_owned_recovery.require_recovered")
    @patch("agency.fenced_owned_recovery.staging_recover", return_value=("unit",))
    @patch("agency.fenced_owned_recovery.os.geteuid", return_value=0)
    def test_gate_runs_after_recovery(self, _uid, recover, gate):
        journal = "/var/lib/hermes-broker/owned-units.sqlite"
        self.assertEqual(recover_owned_journal(journal), ("unit",))
        recover.assert_called_once_with(journal)
        gate.assert_called_once_with(journal)

    @patch("agency.fenced_owned_recovery.require_recovered")
    @patch("agency.fenced_owned_recovery.staging_recover", side_effect=PermissionError)
    @patch("agency.fenced_owned_recovery.os.geteuid", return_value=0)
    def test_recovery_failure_does_not_pass_gate(self, _uid, _recover, gate):
        with self.assertRaises(PermissionError):
            recover_owned_journal("/var/lib/hermes-broker/owned-units.sqlite")
        gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
