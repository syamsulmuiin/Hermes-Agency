"""Dependency-injected checks of existing production evidence bindings."""
import os
import tempfile
import unittest
from unittest.mock import patch

from agency.production_existing_evidence import ExistingProductionEvidence
from agency.production_maintenance_adapter import MaintenanceDenied
from tests.test_portable_production_backend import MANIFEST, resolver


class ExistingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.resolved = resolver(MANIFEST)
        self.calls = []
        def runtime(manifest, resolver):
            self.calls.append("runtime")
            return {"runtime_identity": "PASS", "freeze_present": True,
                    "cutover_authorized": False, "admission_behavior": "NOT_ATTESTED",
                    "snapshot": self.resolved["paths"]["snapshot"]}
        def recovery(manifest, resolver):
            self.calls.append("recovery")
            return {"installed_recovery_wiring": "PASS",
                    "pid1_behavior": "NOT_ATTESTED", "cutover_authorized": False}
        self.evidence = ExistingProductionEvidence(
            MANIFEST, resolver=resolver, runtime_capture=runtime,
            recovery_inspect=recovery, startup_gate=lambda path: True)

    def test_runtime_identity_uses_existing_capture(self):
        self.assertEqual(self.evidence.runtime_identity(self.resolved)["runtime_identity"], "PASS")
        self.assertEqual(self.calls, ["runtime"])

    def test_recovery_wiring_is_not_behavioral_attestation(self):
        self.assertEqual(self.evidence.recovery_wiring(self.resolved)["pid1_behavior"],
                         "NOT_ATTESTED")

    def test_manifest_mismatch_denied(self):
        altered = dict(self.resolved, paths={})
        with self.assertRaises(MaintenanceDenied):
            self.evidence.runtime_identity(altered)

    def test_missing_journal_denied_without_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "absent.sqlite")
            with self.assertRaises(MaintenanceDenied):
                self.evidence.journal_ready(self.resolved, path)
            self.assertFalse(os.path.lexists(path))

    def test_freeze_missing_denied(self):
        with self.assertRaises(FileNotFoundError):
            self.evidence.freeze_verified(self.resolved)


if __name__ == "__main__":
    unittest.main()
