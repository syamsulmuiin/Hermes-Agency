"""Fail-closed production ownership journal bootstrap, requiring exclusive broker stop.

No systemd changes. Invoke only during an authorized maintenance window
after BOTH broker instances are confirmed stopped and admission frozen.
"""
import argparse
import os
import stat
import subprocess

from .fenced_unit_journal import _connect, _verify_store
from .fenced_startup_gate import require_recovered

JOURNAL = "/var/lib/hermes-broker/owned-units.sqlite"


def _inactive(unit):
    result = subprocess.run(
        ["/usr/bin/systemctl", "is-active", unit],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=5, check=False)
    return result.returncode in (0, 3) and result.stdout.strip() in (b"inactive", b"failed")


def bootstrap():
    if os.geteuid() != 0:
        raise PermissionError("Root required")
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
    bootstrap()


if __name__ == "__main__":
    main()
