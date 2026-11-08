"""Safety regression tests for the six-blocker acceptance bundle."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from agency.production_six_blocker_acceptance import (
    BLOCKERS, STAGING_MARKERS, assess, collect, parse_staging_log,
)


class AcceptanceBundleTests(unittest.TestCase):
    def test_missing_staging_is_not_pass(self):
        self.assertEqual(parse_staging_log(None)["status"], "NOT_SUPPLIED")

    def test_staging_markers_are_not_production_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "staging.log"
            path.write_text("\n".join(STAGING_MARKERS) + "\n", encoding="utf-8")
            staging = parse_staging_log(path)
            self.assertEqual(staging["status"], "PASS")
            six, _, _ = assess({"stdout": ""}, staging)
            self.assertEqual(tuple(six), BLOCKERS)
            self.assertTrue(all(v["status"] == "NOT_ATTESTED" for v in six.values()))

    def test_missing_staging_marker_is_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "staging.log"
            path.write_text(STAGING_MARKERS[0] + "\n", encoding="utf-8")
            self.assertEqual(parse_staging_log(path)["status"], "UNVERIFIED")

    def test_stage1_claims_do_not_promote_unattested_behavior(self):
        lines = "\n".join((
            "STAGE1_EVIDENCE=OWNERSHIP_RECOVERY_GATE=PASS",
            "STAGE1_EVIDENCE=SIDECAR_ADMISSION_BEHAVIOR=PASS",
            "STAGE1_EVIDENCE=PID1_RECOVERY_BEHAVIOR=PASS",
            "STAGE1_EVIDENCE=PRODUCTION_BOOT_FROM_EMPTY_RUN=PASS",
        ))
        six, _, _ = assess({"stdout": lines}, {"status": "PASS"})
        self.assertEqual(six["exclusive_drain_inode"]["status"], "NOT_ATTESTED")
        self.assertEqual(six["production_route_handover_rollback"]["status"], "NOT_ATTESTED")

    def test_collect_is_read_only_and_never_go(self):
        commands = []
        def fake_runner(argv, **kwargs):
            commands.append(argv)
            return subprocess.CompletedProcess(argv, 2, "STAGE1_RESULT=NO_GO\n", "")
        report = collect(runner=fake_runner)
        self.assertEqual(len(commands), 2)
        self.assertTrue(all("--execute" not in argv for argv in commands))
        self.assertEqual(report["decision"], "NO_GO")
        self.assertIs(report["production_mutated_by_bundle"], False)
        self.assertIs(report["production_cutover_go"], False)


if __name__ == "__main__":
    unittest.main()
