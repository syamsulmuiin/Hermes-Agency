"""Fail-closed production ownership journal bootstrap, requiring exclusive broker stop.

No systemd changes. Invoke only during an authorized maintenance window
after BOTH broker instances are confirmed stopped and admission frozen.
"""
import argparse
import contextlib
import os
import stat
import subprocess

from .production_admission_drain import exclusive_admission_drain
from .fenced_unit_journal import _connect, _verify_store
from .fenced_startup_gate import require_recovered

JOURNAL = "/var/lib/hermes-broker/owned-units.sqlite"


def _inactive(unit):
    """Require systemd to confirm no active process or queued job."""
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "show", unit,
             "--property=LoadState", "--property=ActiveState",
             "--property=MainPID", "--property=Job"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    fields = dict(line.split("=", 1) for line in result.stdout.decode(
        "ascii", "replace").splitlines() if "=" in line)
    return (fields.get("LoadState") == "loaded"
            and fields.get("ActiveState") in ("inactive", "failed")
            and fields.get("MainPID") == "0"
            and fields.get("Job") in ("", "0"))


def bootstrap(*, admission_drained=False):
    if os.geteuid() != 0:
        raise PermissionError("Root required")
    if not admission_drained:
        raise PermissionError("Exclusive admission drain required")
    freeze = "/run/hermes-operator/admission.freeze"
    info = os.lstat(freeze)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        raise PermissionError("Unsafe admission freeze marker")
    for unit in ("hermes-signed-broker.service",
                 "hermes-fenced-broker-candidate.service"):
        if not _inactive(unit):
            raise PermissionError("Broker not confirmed stopped: " + unit)
    _verify_store(JOURNAL)
    if os.path.lexists(JOURNAL):
        raise PermissionError("Refusing to overwrite existing ownership journal")
    with _connect(JOURNAL) as db:
        count = db.execute("SELECT COUNT(*) FROM owned_units").fetchone()[0]
        if count:
            raise PermissionError("Unexpected pending units")
    directory = os.open(os.path.dirname(JOURNAL), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    require_recovered(JOURNAL)
    print("PRODUCTION_OWNERSHIP_BOOTSTRAP=PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker-stopped", action="store_true", required=True)
    args = parser.parse_args()
    if not args.broker_stopped:
        raise PermissionError("Explicit stopped broker assertion required")
    with exclusive_admission_drain(timeout=30):
        bootstrap(admission_drained=True)


if __name__ == "__main__":
    main()
