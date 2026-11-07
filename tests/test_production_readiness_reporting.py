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

    def test_stage2_remains_plan_only(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = stages.stage2_plan()
        self.assertEqual(result, 2)
        self.assertIn("STAGE2_EXECUTION=DISABLED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
