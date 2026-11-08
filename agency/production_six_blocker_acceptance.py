"""Read-only six-blocker production acceptance evidence bundle.

Runs existing read-only probes; staging E2E is deliberately NOT executed here.
A PASS in staging never authorizes production cutover.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

BLOCKERS = (
    "ownership_journal",
    "live_sidecar_admission",
    "exclusive_drain_inode",
    "production_route_handover_rollback",
    "independent_pid1_recovery",
    "empty_run_boot_provisioning",
)
COMMANDS = (
    ("stage1", (sys.executable, "-B", "-m", "agency.production_readiness_stages", "--stage1-read-only")),
    ("cutover_gate", (sys.executable, "-B", "-m", "agency.fenced_cutover_controller", "--dry-run")),
)
STAGING_MARKERS = (
    "COMBINED_REAL_SOCKET_HANDOVER_RESTART_REPLAY=PASS",
    "COMBINED_REAL_SOCKET_ROLLBACK_LEDGER=PASS",
    "COMBINED_REAL_SOCKET_CUTOVER_E2E=PASS",
    "PRODUCTION_CUTOVER_GO=NO",
)


def parse_staging_log(path):
    if path is None:
        return {"status": "NOT_SUPPLIED", "note": "Staging PASS is not production attestation"}
    source = Path(path)
    if not source.is_file() or source.is_symlink() or source.stat().st_size > 1024 * 1024:
        raise ValueError("Staging log must be a regular non-symlink file <= 1 MiB")
    lines = set(source.read_text(encoding="utf-8").splitlines())
    return {"status": "PASS" if all(marker in lines for marker in STAGING_MARKERS) else "UNVERIFIED",
            "required_markers": list(STAGING_MARKERS),
            "note": "External staging output, not independently authenticated production evidence"}


def probe(label, argv, runner=subprocess.run):
    try:
        result = runner(list(argv), capture_output=True, text=True, timeout=45, check=False)
        return {"returncode": result.returncode, "stdout": result.stdout[-20000:],
                "stderr": result.stderr[-2000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": None, "error": type(exc).__name__}


def assess(stage1, staging):
    output = stage1.get("stdout", "")
    evidence = [line[len("STAGE1_EVIDENCE="):] for line in output.splitlines()
                if line.startswith("STAGE1_EVIDENCE=")]
    blockers = [line[len("STAGE1_BLOCKER="):] for line in output.splitlines()
                if line.startswith("STAGE1_BLOCKER=")]
    observed = {
        "ownership_journal": "OWNERSHIP_RECOVERY_GATE=PASS" in evidence,
        "live_sidecar_admission": any(line == "SIDECAR_ADMISSION_BEHAVIOR=PASS" for line in evidence),
        "exclusive_drain_inode": False,
        "production_route_handover_rollback": False,
        "independent_pid1_recovery": any(line == "PID1_RECOVERY_BEHAVIOR=PASS" for line in evidence),
        "empty_run_boot_provisioning": any(line == "PRODUCTION_BOOT_FROM_EMPTY_RUN=PASS" for line in evidence),
    }
    # Existing stage1 deliberately does not attest exclusive drain, route or
    # boot behavior; never infer those from unrelated staging tests.
    return {
        key: {"status": "OBSERVED_ONLY_NOT_AUTHORIZED" if observed[key] else "NOT_ATTESTED",
              "staging_e2e": staging["status"] if key in (
                  "ownership_journal", "production_route_handover_rollback") else "NOT_APPLICABLE"}
        for key in BLOCKERS
    }, evidence, blockers


def collect(staging_log=None, runner=subprocess.run):
    probes = {name: probe(name, command, runner) for name, command in COMMANDS}
    staging = parse_staging_log(staging_log)
    six, evidence, blockers = assess(probes["stage1"], staging)
    return {
        "schema": "hermes-six-blocker-acceptance-v1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "production_mutated_by_bundle": False,
        "production_cutover_go": False,
        "decision": "NO_GO",
        "staging": staging,
        "blockers": six,
        "stage1_evidence": evidence,
        "stage1_blockers": blockers,
        "probes": probes,
        "note": "Evidence report only. Does not attest live sidecar behavior, execute staging or authorize maintenance.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-log", help="Optional existing staging output; no staging commands executed")
    parser.add_argument("--output", help="Write JSON report to a NEW local file (exclusive create)")
    args = parser.parse_args(argv)
    report = collect(args.staging_log)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
    else:
        print(payload, end="")
    print("ACCEPTANCE_RESULT=NO_GO", file=sys.stderr)
    print("PRODUCTION_MUTATED=NO", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
