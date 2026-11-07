"""Fail-closed production cutover gate: read-only planning only.

No --execute mode exists. A successful staging test is never a production
cutover authorization.
"""
import argparse
import os
from pathlib import Path
import stat
import subprocess
import sys

from .fenced_snapshot_acceptance_preflight import SNAPSHOT, audit as snapshot_audit
from .production_readiness_stages import audit as readiness_audit

LOCK = Path("/run/hermes-admission/admission.lock")
FREEZE = Path("/run/hermes-operator/admission.freeze")
JOURNAL = Path("/var/lib/hermes-broker/owned-units.sqlite")
UNITS = ("hermes-fenced-broker-candidate.service",
         "hermes-fenced-recovery-candidate.service")


def show(unit, prop):
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", unit, "-p", prop, "--value"],
        capture_output=True, text=True, timeout=10, check=False)
    if result.returncode:
        raise RuntimeError("systemctl show failed: " + unit + " " + prop)
    return result.stdout.strip()


def regular_root(path, mode):
    try:
        info = path.lstat()
    except OSError:
        return False
    return (stat.S_ISREG(info.st_mode) and info.st_uid == 0
            and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == mode)


def run():
    blockers = []
    if os.geteuid() != 0:
        blockers.append("Root required for reliable host evidence")
    try:
        snapshot_rc = snapshot_audit(Path("/root/Hermes-Agency"))
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        snapshot_rc = 2
        blockers.append("Snapshot audit exception: " + type(exc).__name__)
    if snapshot_rc:
        blockers.append("Pinned snapshot preflight failed")
    if not FREEZE.exists() or FREEZE.is_symlink():
        blockers.append("Admission freeze absent or unsafe")
    if not regular_root(LOCK, 0o640):
        blockers.append("Admission lock insecure or absent")
    else:
        info = LOCK.stat()
        print("CUTOVER_LOCK_INODE=" + str(info.st_dev) + ":" + str(info.st_ino))
    if not regular_root(JOURNAL, 0o600):
        blockers.append("Ownership journal not safely provisioned")
    for unit in UNITS:
        try:
            directory = show(unit, "WorkingDirectory")
            if directory != str(SNAPSHOT):
                blockers.append(unit + " installed WorkingDirectory mismatch")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            blockers.append(unit + " wiring unavailable: " + type(exc).__name__)
    try:
        stage1_rc = readiness_audit()
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        stage1_rc = 2
        blockers.append("Stage1 exception: " + type(exc).__name__)
    if stage1_rc:
        blockers.append("Stage1 production readiness not attested")
    # These cannot be proven by a read-only inspection and must be
    # independently accepted during a controlled maintenance process.
    blockers.extend((
        "Live sidecar admission and exclusive drain not behaviorally attested",
        "Broker quiescence and persistent lock ownership not attested",
        "Production handover and rollback not acceptance-tested",
        "Empty /run boot provisioning not attested",
    ))
    for item in blockers:
        print("CUTOVER_CONTROLLER_BLOCKER=" + item)
    print("CUTOVER_CONTROLLER_MODE=READ_ONLY")
    print("CUTOVER_CONTROLLER_EXECUTION=DISABLED")
    print("CUTOVER_CONTROLLER_RESULT=NO_GO")
    print("PRODUCTION_MUTATED=NO")
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
