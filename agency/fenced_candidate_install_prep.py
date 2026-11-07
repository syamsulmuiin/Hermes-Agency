"""One-command read-only preparation gate for fenced candidate installation.

Does not install units, daemon-reload, start, stop, enable, or provision state.
Snapshot bytes are compared with independently pinned Git objects.
"""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys

from .fenced_final_manifest_audit import audit as static_manifest_audit
from .production_cutover_preflight import EXPECTED_PIN

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = Path("/opt/hermes-fenced-" + EXPECTED_PIN)
UNITS = ("hermes-fenced-broker-candidate.service",
         "hermes-fenced-recovery-candidate.service")
# Admission drain is a separately deployed maintenance controller.
# It requires its own attestation before cutover.
SOURCE_FILES = (
    "agency/fenced_broker_candidate.py",
    "agency/fenced_owned_recovery.py",
    "agency/fenced_startup_gate.py",
    "agency/fenced_unit_journal.py",
    "agency/operator_control.py",
)


def command(argv, *, cwd=None):
    return subprocess.run(argv, cwd=cwd, capture_output=True, timeout=20, check=False)


def main():
    blockers = []
    if not static_manifest_audit():
        blockers.append("Static systemd manifest gate failed")
    if not SNAPSHOT.is_dir() or SNAPSHOT.is_symlink():
        blockers.append("Pinned snapshot absent or symlink")
    else:
        for name in SOURCE_FILES:
            target = SNAPSHOT / name
            try:
                info = target.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise PermissionError("not a regular single-link file")
                pinned = command(["git", "show", EXPECTED_PIN + ":" + name], cwd=ROOT)
                if pinned.returncode:
                    blockers.append("Pinned Git object unavailable: " + name)
                    continue
                actual = hashlib.sha256(target.read_bytes()).digest()
                expected = hashlib.sha256(pinned.stdout).digest()
                if actual != expected:
                    blockers.append("Snapshot differs from pinned Git object: " + name)
                else:
                    print("PINNED_SOURCE_MATCH=" + name)
            except (OSError, PermissionError, subprocess.TimeoutExpired) as exc:
                blockers.append("Snapshot file not verifiable: " + name + " " + type(exc).__name__)
    print("SEPARATE_ATTESTATION_REQUIRED=agency/production_admission_drain.py")
    for unit in UNITS:
        path = ROOT / "deploy/systemd" / unit
        try:
            result = command(["systemd-analyze", "verify", str(path)])
            if result.returncode:
                blockers.append("systemd-analyze verify failed: " + unit)
                print("SYSTEMD_VERIFY_DETAIL=" + result.stderr.decode("utf-8", "replace")[:600])
            else:
                print("SYSTEMD_VERIFY_PASS=" + unit)
        except (OSError, subprocess.TimeoutExpired) as exc:
            blockers.append("systemd verification unavailable: " + unit + " " + type(exc).__name__)
    for unit in UNITS:
        installed = Path("/etc/systemd/system") / unit
        if installed.exists() or installed.is_symlink():
            blockers.append("Candidate unit already installed; manual review required: " + unit)
    for item in blockers:
        print("CANDIDATE_PREP_BLOCKER=" + item)
    print("CANDIDATE_INSTALL_PREP=" + ("PASS" if not blockers else "NO_GO"))
    print("CANDIDATE_INSTALL_EXECUTED=NO")
    print("PRODUCTION_MUTATED=NO")
    return 0 if not blockers else 2


if __name__ == "__main__":
    sys.exit(main())
