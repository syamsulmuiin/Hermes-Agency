"""Readiness reporting must not promote external tests into cutover approval."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from agency import production_readiness_stages as stages


class ReadinessReportTests(unittest.TestCase):
    def test_external_tests_are_unattested_and_cutover_remains_blocked(self):
        with patch.object(stages, "_show", side_effect=PermissionError("isolated")), \
             patch.object(stages, "_regular", return_value=False), \
             patch.object(stages.pathlib.Path, "is_dir", return_value=False):
            output = io.StringIO()
            with redirect_stdout(output):
                result = stages.audit()
        report = output.getvalue()
        self.assertEqual(result, 2)
        for item in (
            "CANDIDATE_ROUTE_UNIT_TESTS=EXTERNAL_RESULT_NOT_ATTESTED",
            "TMPFILES_EMPTY_DIRECTORY_TEST=EXTERNAL_RESULT_NOT_ATTESTED",
            "LIVE_ADMISSION_FLOCK_TEST=EXTERNAL_RESULT_NOT_ATTESTED",
            "PRODUCTION_BOOT_FROM_EMPTY_RUN=NOT_TESTED",
            "Admission provisioning boot from empty /run not attested",
            "Ownership journal not securely provisioned",
            "Production-route handover and rollback not acceptance-tested",
            "STAGE1_RESULT=NO_GO",
            "PRODUCTION_MUTATED=NO",
        ):
            self.assertIn(item, report)

    def test_runtime_evidence_never_promotes_stage1(self):
        with patch.object(stages, "_show", side_effect=PermissionError("isolated")), \
             patch.object(stages, "_regular", return_value=False), \
             patch.object(stages.pathlib.Path, "is_dir", return_value=False), \
             patch("agency.production_runtime_evidence.capture", return_value={
                 "runtime_identity": "PASS", "sidecar_pid": 1234,
                 "snapshot": "/opt/hermes-fenced-9bf261261b59",
                 "admission_behavior": "NOT_ATTESTED",
                 "cutover_authorized": False,
             }):
            output = io.StringIO()
            with redirect_stdout(output):
                result = stages.audit()
        self.assertEqual(result, 2)
        self.assertIn("SIDECAR_RUNTIME_IDENTITY=PASS", output.getvalue())
        self.assertIn("STAGE1_RESULT=NO_GO", output.getvalue())

    def test_runtime_capture_failure_is_blocker(self):
        with patch.object(stages, "_show", side_effect=PermissionError("isolated")), \
             patch.object(stages, "_regular", return_value=False), \
             patch.object(stages.pathlib.Path, "is_dir", return_value=False), \
             patch("agency.production_runtime_evidence.capture",
                   side_effect=PermissionError("runtime unavailable")):
            output = io.StringIO()
            with redirect_stdout(output):
                result = stages.audit()
        self.assertEqual(result, 2)
        self.assertIn("Sidecar runtime identity not independently attested",
                      output.getvalue())

    def test_snapshot_manifest_pass_is_observed_not_authorized(self):
        with patch.object(stages, "_show", side_effect=PermissionError("isolated")), \
             patch.object(stages, "_regular", return_value=False), \
             patch.object(stages.pathlib.Path, "is_dir", return_value=True), \
             patch.object(stages.pathlib.Path, "is_symlink", return_value=False), \
             patch("agency.fenced_snapshot_acceptance_preflight.audit", return_value=0), \
             patch("agency.production_runtime_evidence.capture",
                   side_effect=PermissionError("isolated")):
            output = io.StringIO()
            with redirect_stdout(output):
                result = stages.audit()
        self.assertEqual(result, 2)
        self.assertIn("CANDIDATE_CONTENT_MANIFEST=PASS", output.getvalue())
        self.assertIn("STAGE1_RESULT=NO_GO", output.getvalue())

    def test_snapshot_manifest_failure_stays_blocked(self):
        with patch.object(stages, "_show", side_effect=PermissionError("isolated")), \
             patch.object(stages, "_regular", return_value=False), \
             patch.object(stages.pathlib.Path, "is_dir", return_value=True), \
             patch.object(stages.pathlib.Path, "is_symlink", return_value=False), \
             patch("agency.fenced_snapshot_acceptance_preflight.audit", return_value=2), \
             patch("agency.production_runtime_evidence.capture",
                   side_effect=PermissionError("isolated")):
            output = io.StringIO()
            with redirect_stdout(output):
                result = stages.audit()
        self.assertEqual(result, 2)
        self.assertIn("Candidate content digest and deployment manifest not attested",
                      output.getvalue())

    def test_installed_recovery_wiring_does_not_clear_pid1_blocker(self):
        with patch.object(stages, "_show", side_effect=PermissionError("isolated")), \
             patch.object(stages, "_regular", return_value=False), \
             patch.object(stages.pathlib.Path, "is_dir", return_value=False), \
             patch("agency.production_recovery_wiring_evidence.inspect",
                   return_value={"installed_recovery_wiring": "PASS",
                                 "pid1_behavior": "NOT_ATTESTED",
                                 "cutover_authorized": False}), \
             patch("agency.production_runtime_evidence.capture",
                   side_effect=PermissionError("isolated")):
            output = io.StringIO()
            with redirect_stdout(output):
                result = stages.audit()
        self.assertEqual(result, 2)
        self.assertIn("INSTALLED_PID1_RECOVERY_WIRING=PASS", output.getvalue())
        self.assertIn("Independent PID1 recovery wiring for deployed candidate not attested",
                      output.getvalue())

    def test_stage2_remains_plan_only(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = stages.stage2_plan()
        self.assertEqual(result, 2)
        self.assertIn("STAGE2_EXECUTION=DISABLED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
