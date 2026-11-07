"""Read-only candidate deployment parity checks; fail closed on stale /opt source."""
import argparse
import os
from pathlib import Path
import subprocess

MODULES = (
    "agency/fenced_broker_candidate.py",
    "agency/fenced_startup_gate.py",
    "agency/fenced_owned_recovery.py",
    "agency/fenced_systemd_supervisor.py",
    "agency/fenced_staging_launcher.py",
    "agency/fenced_staging_broker.py",
    "agency/fenced_unit_journal.py",
)


def check(source, deployed):
    source = Path(source).resolve(strict=True)
    deployed = Path(deployed).resolve(strict=True)
    if source == deployed:
        raise PermissionError("Deployment must be separate from development checkout")
    if not deployed.is_dir():
        raise PermissionError("Deployment root missing")
    missing = []
    mismatched = []
    for relative in MODULES:
        src = source / relative
        dst = deployed / relative
        if not src.is_file() or not dst.is_file():
            missing.append(relative)
        elif src.read_bytes() != dst.read_bytes():
            mismatched.append(relative)
    if missing:
        print("CANDIDATE_DEPLOYMENT_MISSING=" + ",".join(missing), flush=True)
    if mismatched:
        print("CANDIDATE_DEPLOYMENT_STALE=" + ",".join(mismatched), flush=True)
    if missing or mismatched:
        raise PermissionError("Candidate deployment does not match checked source")
    result = subprocess.run(
        ["/usr/bin/python3", "-c",
         "import agency.fenced_broker_candidate as b; print(b.__file__)"],
        cwd=deployed, capture_output=True, text=True, timeout=10, check=False,
        env={**os.environ, "PYTHONPATH": str(deployed)})
    expected = str(deployed / "agency/fenced_broker_candidate.py")
    if result.returncode or result.stdout.strip() != expected:
        raise PermissionError("Deployed Python module import mismatch")
    print("CANDIDATE_DEPLOYMENT_PARITY=PASS", flush=True)
    print("PRODUCTION_CUTOVER_EXECUTED=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/root/Hermes-Agency")
    parser.add_argument("--deployed", default="/opt/hermes-agency")
    args = parser.parse_args(argv)
    check(args.source, args.deployed)


if __name__ == "__main__":
    main()
