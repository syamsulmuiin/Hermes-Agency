"""Prepare a versioned candidate deployment from the checked-out GitHub source.

Never modifies /opt/hermes-agency, systemd units, credentials or live data.
A unique staging directory is created under /opt and can be inspected before
any explicit cutover. Only a clean, pinned Git checkout is accepted.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .fenced_deployment_parity import MODULES


def git(source, *args):
    result = subprocess.run(
        ["git", "-C", str(source), *args], capture_output=True, text=True,
        timeout=30, check=True)
    return result.stdout.strip()


def prepare(source, destination_root, execute=False):
    source = Path(source).resolve(strict=True)
    root = Path(destination_root).resolve(strict=True)
    if os.geteuid() != 0:
        raise PermissionError("Root required for candidate deployment")
    if git(source, "status", "--porcelain"):
        raise PermissionError("Dirty source checkout; commit changes first")
    if git(source, "rev-parse", "--abbrev-ref", "HEAD") != "development/foundation":
        raise PermissionError("Unexpected source branch")
    revision = git(source, "rev-parse", "HEAD")
    if not revision or len(revision) != 40:
        raise PermissionError("Invalid source revision")
    destination = root / ("hermes-fenced-" + revision[:12])
    if destination.exists():
        raise FileExistsError("Candidate revision already deployed: " + str(destination))
    print("CANDIDATE_SOURCE_REVISION=" + revision, flush=True)
    print("CANDIDATE_DEPLOYMENT_TARGET=" + str(destination), flush=True)
    if not execute:
        print("CANDIDATE_DEPLOYMENT_EXECUTED=NO", flush=True)
        return
    with tempfile.TemporaryDirectory(prefix=".hermes-fenced-", dir=root) as staging:
        staging = Path(staging)
        subprocess.run(
            ["git", "clone", "--quiet", "--no-hardlinks", "--local",
             str(source), str(staging / "source")],
            check=True, timeout=90)
        checkout = staging / "source"
        subprocess.run(["git", "-C", str(checkout), "checkout", "--quiet", "--detach",
                        revision], check=True, timeout=30)
        if git(checkout, "rev-parse", "HEAD") != revision:
            raise PermissionError("Candidate revision mismatch")
        for relative in MODULES:
            if (source / relative).read_bytes() != (checkout / relative).read_bytes():
                raise PermissionError("Candidate module mismatch: " + relative)
        # Atomic publication only after all checks; existing live tree untouched.
        os.rename(checkout, destination)
    print("CANDIDATE_DEPLOYMENT_PREPARED=PASS", flush=True)
    print("PRODUCTION_CUTOVER_EXECUTED=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/root/Hermes-Agency")
    parser.add_argument("--destination-root", default="/opt")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    prepare(args.source, args.destination_root, args.execute)


if __name__ == "__main__":
    main()
