"""Installed PID1 recovery wiring must fail closed."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from agency import production_recovery_wiring_evidence as evidence


class RecoveryWiringTests(unittest.TestCase):
    def states(self):
        broker = {
            "LoadState": "loaded", "WorkingDirectory": evidence.SNAPSHOT,
            "User": "root",
            "OnFailure": evidence.RECOVERY,
            "Requires": evidence.RECOVERY,
            "After": evidence.RECOVERY,
            "ExecStartPre": "python3 -m agency.fenced_startup_gate",
            "ExecStopPost": "python3 -m agency.fenced_owned_recovery",
        }
        recovery = {
            "LoadState": "loaded", "WorkingDirectory": evidence.SNAPSHOT,
            "User": "root",
            "ExecStart": "python3 -m agency.fenced_owned_recovery",
        }
        return broker, recovery

    def test_valid_wiring_is_not_behavioral_attestation(self):
        with patch.object(evidence, "_show", side_effect=self.states()):
            report = evidence.inspect()
        self.assertEqual(report["installed_recovery_wiring"], "PASS")
        self.assertEqual(report["pid1_behavior"], "NOT_ATTESTED")
        self.assertFalse(report["cutover_authorized"])

    def test_each_missing_dependency_denied(self):
        for field in ("OnFailure", "Requires", "After",
                      "ExecStartPre", "ExecStopPost"):
            with self.subTest(field=field):
                broker, recovery = self.states()
                broker[field] = ""
                with patch.object(evidence, "_show",
                                  side_effect=[broker, recovery]):
                    with self.assertRaises(PermissionError):
                        evidence.inspect()

    def test_untrusted_recovery_user_denied(self):
        broker, recovery = self.states()
        recovery["User"] = "hermes-worker"
        with patch.object(evidence, "_show", side_effect=[broker, recovery]):
            with self.assertRaises(PermissionError):
                evidence.inspect()

    def test_cli_never_returns_go(self):
        with patch.object(evidence, "_show", side_effect=self.states()):
            with redirect_stdout(io.StringIO()) as output:
                rc = evidence.main(["--read-only"])
        self.assertEqual(rc, 2)
        self.assertIn("PID1_BEHAVIOR=NOT_ATTESTED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
