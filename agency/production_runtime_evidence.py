"""Read-only runtime evidence capture; never grants production cutover authorization.

Evidence is deliberately ephemeral: callers must re-check identity and inode
at the point of use. This module never reads credentials or modifies services.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

SNAPSHOT = Path("/opt/hermes-fenced-9bf261261b59")
LOCK = Path("/run/hermes-admission/admission.lock")
FREEZE = Path("/run/hermes-operator/admission.freeze")
SIDECAR = "hermes-operator-sidecar.service"


def _show(unit, *properties):
    cmd = ["/usr/bin/systemctl", "show", unit]
    cmd.extend("--property=" + key for key in properties)
    result = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=10, check=True)
    return dict(line.split("=", 1) for line in result.stdout.splitlines()
                if "=" in line)


def capture():
    """Return bounded non-secret runtime observations; fail closed."""
    state = _show(SIDECAR, "ActiveState", "MainPID", "WorkingDirectory",
                  "Environment", "User", "Group")
    pid = int(state.get("MainPID", "0"))
    if state.get("ActiveState") != "active" or pid <= 1:
        raise PermissionError("Sidecar is not active")
    if state.get("User") != "hermes-trusted":
        raise PermissionError("Unexpected sidecar user")
    if state.get("WorkingDirectory") != str(SNAPSHOT):
        raise PermissionError("Sidecar working directory mismatch")
    if "PYTHONPATH=" + str(SNAPSHOT) not in state.get("Environment", "").split():
        raise PermissionError("Sidecar Python path mismatch")
    if SNAPSHOT.is_symlink() or not SNAPSHOT.is_dir():
        raise PermissionError("Snapshot missing or linked")
    cwd = os.readlink("/proc/%d/cwd" % pid)
    if cwd != str(SNAPSHOT):
        raise PermissionError("Running sidecar snapshot mismatch")
    cmdline = Path("/proc/%d/cmdline" % pid).read_bytes().split(b"\0")
    if b"agency.operator_service" not in cmdline:
        raise PermissionError("Unexpected sidecar entrypoint")
    if not FREEZE.exists() or FREEZE.is_symlink():
        raise PermissionError("Production freeze missing")
    info = LOCK.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o640):
        raise PermissionError("Admission lock insecure")
    # Detect inode replacement during capture.
    again = LOCK.lstat()
    if (info.st_dev, info.st_ino) != (again.st_dev, again.st_ino):
        raise PermissionError("Admission lock changed during capture")
    return {"sidecar_pid": pid, "snapshot": str(SNAPSHOT),
            "lock_device": info.st_dev, "lock_inode": info.st_ino,
            "freeze_present": True, "runtime_identity": "PASS",
            "admission_behavior": "NOT_ATTESTED",
            "production_handover": "NOT_TESTED",
            "cutover_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        report = capture()
    except (OSError, ValueError, PermissionError, subprocess.SubprocessError) as exc:
        print("RUNTIME_EVIDENCE=NO_GO")
        print("EVIDENCE_ERROR=" + type(exc).__name__)
        print("PRODUCTION_MUTATED=NO")
        return 2
    print(json.dumps(report, sort_keys=True))
    print("RUNTIME_EVIDENCE=OBSERVED_NOT_AUTHORIZED")
    print("PRODUCTION_MUTATED=NO")
    return 2


if __name__ == "__main__":
    sys.exit(main())
