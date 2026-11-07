"""Install INACTIVE fenced candidate systemd units after read-only attestation.

No start, enable, broker routing, journal creation, or admission lock mutation.
Explicit root invocation required; rollback removes only units created here.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

from .fenced_candidate_install_prep import main as preparation_gate, ROOT, SNAPSHOT, UNITS

UNIT_DIR = Path("/etc/systemd/system")


def check_drain_source():
    path = ROOT / "agency/production_admission_drain.py"
    if path.is_symlink() or not path.is_file():
        raise PermissionError("Missing safe admission drain source")
    data = path.read_bytes()
    pinned = subprocess.run(
        ["git", "show", "HEAD:agency/production_admission_drain.py"],
        cwd=ROOT, capture_output=True, timeout=10, check=False)
    if pinned.returncode or hashlib.sha256(data).digest() != hashlib.sha256(pinned.stdout).digest():
        raise PermissionError("Admission drain source differs from current committed revision")
    print("ADMISSION_DRAIN_SOURCE=COMMITTED_MATCH")
    print("ADMISSION_DRAIN_LIVE_RUNTIME_ATTESTED=NO")


def check_snapshot():
    info = SNAPSHOT.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise PermissionError("Unsafe candidate snapshot directory")
    for name in ("agency", "agency/fenced_broker_candidate.py",
                 "agency/fenced_owned_recovery.py", "agency/fenced_startup_gate.py"):
        target = SNAPSHOT / name
        info = target.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError("Unsafe candidate ownership or writable permissions: " + name)
        if name == "agency":
            if not stat.S_ISDIR(info.st_mode):
                raise PermissionError("Unsafe candidate package directory")
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PermissionError("Unsafe candidate file type: " + name)
    print("SNAPSHOT_PERMISSION_GATE=PASS")


def install():
    if os.geteuid() != 0:
        raise PermissionError("Root required")
    if preparation_gate() != 0:
        raise PermissionError("Candidate preparation gate failed")
    check_drain_source()
    check_snapshot()
    parent = UNIT_DIR.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_mode & 0o022:
        raise PermissionError("Unsafe systemd unit directory")
    for name in UNITS:
        if os.path.lexists(UNIT_DIR / name):
            raise PermissionError("Refusing to replace existing unit: " + name)
    # Create units exclusively, never overwrite. If installation fails, remove
    # only files created by this invocation and reload PID1 unit metadata.
    created = []
    try:
        for name in UNITS:
            src = ROOT / "deploy/systemd" / name
            if src.is_symlink() or not src.is_file():
                raise PermissionError("Unsafe source unit: " + name)
            payload = src.read_bytes()
            fd = os.open(str(UNIT_DIR / name),
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o644)
            created.append((UNIT_DIR / name, os.fstat(fd).st_ino))
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(UNIT_DIR / name, 0o644)
        result = subprocess.run(["/usr/bin/systemctl", "daemon-reload"], timeout=20, check=False)
        if result.returncode:
            raise RuntimeError("systemd daemon-reload failed")
        for name in UNITS:
            state = subprocess.run(
                ["/usr/bin/systemctl", "show", name, "--property=LoadState",
                 "--property=ActiveState", "--property=UnitFileState"],
                capture_output=True, text=True, timeout=10, check=False)
            fields = dict(line.split("=", 1) for line in state.stdout.splitlines() if "=" in line)
            if (state.returncode or fields.get("LoadState") != "loaded"
                    or fields.get("ActiveState") != "inactive"
                    or fields.get("UnitFileState") not in ("disabled", "static")):
                raise RuntimeError("Candidate must remain loaded, inactive and disabled: " + name)
            print("INSTALLED_INACTIVE=" + name)
    except BaseException:
        for path, inode in reversed(created):
            try:
                if path.lstat().st_ino == inode:
                    path.unlink()
            except FileNotFoundError:
                pass
        subprocess.run(["/usr/bin/systemctl", "daemon-reload"], timeout=20, check=False)
        raise
    print("CANDIDATE_UNITS_INSTALLED=PASS")
    print("CANDIDATE_SERVICES_STARTED=NO")
    print("PRODUCTION_BROKER_ROUTING_CHANGED=NO")


def main(argv=None):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify-only", action="store_true")
    group.add_argument("--install-inactive", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            result = preparation_gate()
            if result:
                return result
            check_drain_source()
            check_snapshot()
            print("INACTIVE_INSTALL_GATE=PASS")
            return 0
        install()
        return 0
    except (OSError, PermissionError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("INACTIVE_INSTALL=NO_GO " + str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
