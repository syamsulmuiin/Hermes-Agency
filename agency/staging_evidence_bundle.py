"""Create a fresh, non-authorizing staging evidence report.

Only tests invoked by this command can be marked PASS. Does not run systemd
acceptance or infer production readiness from operator-supplied claims.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

TESTS = (
    "tests.test_isolated_admission_behavior",
    "tests.test_durable_recovery_gate",
    "tests.test_fenced_owned_recovery",
    "tests.test_fenced_recovery_lifecycle",
    "tests.test_fenced_staging_peer_recovery",
    "tests.test_fenced_unit_recovery",
    "tests.test_production_admission_provision",
)
SNAPSHOT = "/opt/hermes-fenced-9bf261261b59"


def collect(repo):
    if os.geteuid() != 0:
        raise PermissionError("Root test environment required")
    commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True, timeout=10).stdout.strip()
    tests = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *TESTS, "-q"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return {
        "schema": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "candidate_snapshot": SNAPSHOT,
        "test_modules": list(TESTS),
        "unit_test_exit_code": tests.returncode,
        "unit_test_result": "PASS" if tests.returncode == 0 else "FAIL",
        "unit_test_output_tail": (tests.stdout + tests.stderr)[-3000:],
        "isolated_empty_run_provisioning": "EXTERNAL_RESULT_NOT_ATTESTED",
        "isolated_pid1_onfailure": "EXTERNAL_RESULT_NOT_ATTESTED",
        "live_sidecar_admission": "NOT_ATTESTED",
        "production_boot": "NOT_TESTED",
        "production_handover": "NOT_TESTED",
        "cutover_authorized": False,
        "production_mutated": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/root/Hermes-Agency"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.is_symlink() or args.output.exists():
        parser.error("Output must be a new file, not a symlink or existing path")
    report = collect(args.repo)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print("STAGING_UNIT_TESTS=" + report["unit_test_result"])
    print("STAGING_EVIDENCE_FILE=" + str(args.output))
    print("PRODUCTION_CUTOVER_GO=NO")
    print("PRODUCTION_MUTATED=NO")
    return 0 if report["unit_test_exit_code"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
