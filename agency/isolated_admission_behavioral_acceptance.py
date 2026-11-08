"""Behavioral acceptance for isolated admission-lock contention and inode stability.

Never touches /run/hermes-admission, production services, routes or journals.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .production_host_backend import IsolatedHostBackend
from .production_maintenance_adapter import MaintenanceDenied

HOLDER = """
import fcntl, os, sys
fd=os.open(sys.argv[1], os.O_RDONLY|os.O_NOFOLLOW)
fcntl.flock(fd, fcntl.LOCK_SH)
print('HELD', flush=True)
sys.stdin.read(1)
"""


class FixtureOperations:
    def admission_participation_verified(self):
        # Fixture only. This is NOT a live sidecar attestation.
        return True


def exercise():
    with tempfile.TemporaryDirectory(prefix="hermes-behavioral-") as directory:
        root = Path(directory)
        lock = root / "admission.lock"
        freeze = root / "admission.freeze"
        lock.touch(mode=0o640)
        lock.chmod(0o640)
        freeze.touch(mode=0o600)
        freeze.chmod(0o600)
        backend = IsolatedHostBackend(lock, freeze, FixtureOperations())
        holder = subprocess.Popen(
            [sys.executable, "-u", "-c", HOLDER, str(lock)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        try:
            if holder.stdout.readline().strip() != "HELD":
                raise AssertionError("Fixture holder failed to acquire shared lock")
            try:
                with backend.exclusive_drain():
                    raise AssertionError("Exclusive lock acquired while shared holder active")
            except BlockingIOError:
                pass
        finally:
            if holder.stdin:
                holder.stdin.write("x")
                holder.stdin.flush()
                holder.stdin.close()
            holder.wait(timeout=5)
            holder.stdout.close()
            holder.stderr.close()
        if holder.returncode:
            raise AssertionError("Fixture holder failed")
        with backend.exclusive_drain():
            original = backend.lock_identity()
            if original != (lock.stat().st_dev, lock.stat().st_ino):
                raise AssertionError("Lock inode not stable")
            replacement = root / "replacement"
            replacement.touch(mode=0o640)
            replacement.chmod(0o640)
            os.replace(replacement, lock)
            try:
                backend.lock_identity()
            except MaintenanceDenied:
                pass
            else:
                raise AssertionError("Inode replacement was not denied")
        return {
            "isolated_shared_lock_contention": "PASS",
            "isolated_exclusive_drain": "PASS",
            "isolated_inode_replacement_denied": "PASS",
            "live_sidecar_admission": "NOT_ATTESTED",
            "production_exclusive_drain": "NOT_ATTESTED",
            "production_mutated": False,
            "cutover_authorized": False,
        }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolated", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        result = exercise()
    except (OSError, ValueError, AssertionError, MaintenanceDenied,
            subprocess.SubprocessError) as exc:
        print("ISOLATED_BEHAVIORAL_ACCEPTANCE=FAIL")
        print("ERROR=" + type(exc).__name__)
        print("PRODUCTION_MUTATED=NO")
        return 2
    print(json.dumps(result, sort_keys=True))
    print("ISOLATED_BEHAVIORAL_ACCEPTANCE=PASS")
    print("PRODUCTION_MUTATED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
