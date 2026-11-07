"""Read-only, machine-readable fenced acceptance evidence summary.

Operator-reported E2E results are recorded as claims, not independently
attested by this collector. Does not change services or production state.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

SNAPSHOT = Path("/opt/hermes-fenced-9bf261261b59")
SNAPSHOT_COMMIT = "9bf261261b5948bc021780548dfb5a40e68cc76f"
SERVICES = (
    "hermes-agency.service",
    "hermes-signed-broker.service",
    "hermes-operator-sidecar.service",
    "hermes-fenced-broker-candidate.service",
    "hermes-fenced-recovery-candidate.service",
)


def call(*argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=30, check=False)
        return {"exit_code": result.returncode,
                "stdout": result.stdout.strip()[:16000],
                "stderr": result.stderr.strip()[:1000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": type(exc).__name__}


def collect():
    from .fenced_snapshot_acceptance_preflight import audit
    # Capture the existing independent inventory preflight without changing it.
    import contextlib
    import io
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        preflight_exit = audit(Path("/root/Hermes-Agency"))
    status = {}
    for unit in SERVICES:
        status[unit] = call("/usr/bin/systemctl", "is-active", unit)
    staging_dir = Path("/run/systemd/system")
    staging_files = sorted(p.name for pattern in
                           ("hermes-pid1-broker-*.service",
                            "hermes-pid1-recovery-*.service")
                           for p in staging_dir.glob(pattern)) if staging_dir.is_dir() else None
    installed = {}
    for unit in SERVICES[-2:]:
        installed[unit] = call("/usr/bin/systemctl", "show", unit,
                               "--property=WorkingDirectory",
                               "--property=FragmentPath",
                               "--property=ActiveState")
    manifest = {
        "schema": "hermes-fenced-acceptance-evidence-v1",
        "collected_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "snapshot": str(SNAPSHOT),
        "snapshot_commit": SNAPSHOT_COMMIT,
        "development_head": call("git", "-C", "/root/Hermes-Agency",
                                 "rev-parse", "HEAD"),
        "preflight_exit_code": preflight_exit,
        "preflight_output": output.getvalue().splitlines(),
        "service_status": status,
        "candidate_installed_wiring": installed,
        "temporary_pid1_unit_files": staging_files,
        "freeze_present": Path("/run/hermes-operator/admission.freeze").exists(),
        "operator_reported_tests_not_independently_attested": {
            "socket_replay_e2e": "PASS (reported)",
            "patched_pid1_e2e": "PASS (reported)",
            "patched_pid1_exit_code": 0,
            "post_pid1_preflight": "PASS (reported)",
        },
        "production_cutover_authorized": False,
        "production_mutated_by_collector": False,
    }
    print(json.dumps(manifest, indent=2, sort_keys=True))
    # Do not claim readiness on staging-only evidence.
    return 0 if (preflight_exit == 0 and staging_files == [] and
                 manifest["freeze_present"] and
                 all(status[x].get("stdout") == "active" for x in SERVICES[:3]) and
                 all(status[x].get("stdout") == "inactive" for x in SERVICES[3:])) else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)
    return collect()


if __name__ == "__main__":
    sys.exit(main())
