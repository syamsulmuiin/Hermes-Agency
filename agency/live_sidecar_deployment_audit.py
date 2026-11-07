"""Read-only evidence for the currently running operator sidecar deployment.

Never provisions locks, restarts services, or authorizes production cutover.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys

UNIT = "hermes-operator-sidecar.service"
EXPECTED = Path("/run/hermes-admission/admission.lock")


def show(*properties):
    result = subprocess.run(
        ["/usr/bin/systemctl", "show", UNIT, *["--property=" + p for p in properties]],
        capture_output=True, text=True, timeout=10, check=True)
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def audit():
    blockers = []
    state = show("ActiveState", "MainPID", "ExecStart", "FragmentPath",
                 "WorkingDirectory", "Environment", "User")
    pid = int(state.get("MainPID", "0"))
    if state.get("ActiveState") != "active" or pid <= 0:
        blockers.append("Sidecar main process not active")
    else:
        cmd = Path("/proc/%d/cmdline" % pid).read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
        cwd = os.readlink("/proc/%d/cwd" % pid)
        exe = os.readlink("/proc/%d/exe" % pid)
        print("LIVE_SIDECAR_PID=" + str(pid))
        print("LIVE_SIDECAR_EXE=" + exe)
        print("LIVE_SIDECAR_CWD=" + cwd)
        print("LIVE_SIDECAR_CMDLINE=" + cmd[:500])
        if not cmd.strip() or not cwd.startswith("/"):
            blockers.append("Live process identity incomplete")
        # A running Python process may have loaded older bytecode. The on-disk
        # source is NOT proof of its currently loaded code.
        print("LIVE_SIDECAR_LOADED_PYTHON_CODE_ATTESTED=NO")
        blockers.append("Live sidecar lock participation requires runtime behavioral evidence")
    print("LIVE_SIDECAR_UNIT_FRAGMENT=" + state.get("FragmentPath", ""))
    print("LIVE_SIDECAR_UNIT_WORKING_DIRECTORY=" + state.get("WorkingDirectory", ""))
    try:
        info = EXPECTED.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o640):
            blockers.append("Admission lock has unsafe metadata")
        else:
            print("ADMISSION_LOCK_INODE=%s:%s" % (info.st_dev, info.st_ino))
            print("ADMISSION_LOCK_METADATA=PASS")
    except FileNotFoundError:
        blockers.append("Admission lock not provisioned")
    journal = Path("/var/lib/hermes-broker/owned-units.sqlite")
    try:
        info = journal.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            blockers.append("Ownership journal has unsafe metadata")
        else:
            print("OWNERSHIP_JOURNAL_METADATA=PASS")
    except FileNotFoundError:
        blockers.append("Ownership journal not provisioned")
    for unit in ("hermes-fenced-broker-candidate.service",
                 "hermes-fenced-recovery-candidate.service"):
        result = subprocess.run(
            ["/usr/bin/systemctl", "show", unit,
             "--property=LoadState", "--property=ActiveState", "--property=UnitFileState"],
            capture_output=True, text=True, timeout=10, check=True)
        fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        print("CANDIDATE_UNIT=%s LOAD=%s ACTIVE=%s FILE=%s" %
              (unit, fields.get("LoadState"), fields.get("ActiveState"), fields.get("UnitFileState")))
        if (fields.get("LoadState") != "loaded" or fields.get("ActiveState") != "inactive"
                or fields.get("UnitFileState") not in ("static", "disabled")):
            blockers.append("Candidate unit not safely inactive: " + unit)
    for blocker in blockers:
        print("LIVE_DEPLOYMENT_BLOCKER=" + blocker)
    print("LIVE_DEPLOYMENT_ATTESTATION=" + ("PASS" if not blockers else "NO_GO"))
    print("PRODUCTION_MUTATED=NO")
    return 0 if not blockers else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        return audit()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("LIVE_DEPLOYMENT_ATTESTATION=NO_GO " + type(exc).__name__ + ": " + str(exc))
        print("PRODUCTION_MUTATED=NO")
        return 2


if __name__ == "__main__":
    sys.exit(main())
