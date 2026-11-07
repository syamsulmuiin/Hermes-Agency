"""Read-only release alignment report for the accepted fenced runtime.

Development HEAD may advance without invalidating a pinned runtime release.
No service, file, or admission state is changed.
"""
import argparse
from pathlib import Path
import subprocess
import sys

from .fenced_snapshot_acceptance_preflight import COMMIT, SNAPSHOT, audit as snapshot_audit

ROOT = Path("/root/Hermes-Agency")
UNITS = ("hermes-fenced-broker-candidate.service",
         "hermes-fenced-recovery-candidate.service")


def cmd(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          check=False, timeout=20)


def run(repo):
    failures = []
    head = cmd(["git", "rev-parse", "HEAD"], cwd=repo)
    if head.returncode:
        failures.append("Development HEAD unavailable")
    else:
        print("DEVELOPMENT_HEAD=" + head.stdout.strip())
    print("ACCEPTED_RUNTIME_COMMIT=" + COMMIT)
    print("ACCEPTED_RUNTIME_SNAPSHOT=" + str(SNAPSHOT))
    print("DEVELOPMENT_AHEAD_OF_RUNTIME=" +
          ("YES" if head.returncode == 0 and head.stdout.strip() != COMMIT else "NO"))
    print("DEVELOPMENT_DRIFT_INVALIDATES_RUNTIME=NO")
    if snapshot_audit(repo) != 0:
        failures.append("Pinned runtime snapshot acceptance failed")
    for unit in UNITS:
        source = repo / "deploy/systemd" / unit
        installed = Path("/etc/systemd/system") / unit
        try:
            source_bytes = source.read_bytes()
            installed_bytes = installed.read_bytes()
            if source_bytes != installed_bytes:
                failures.append("Installed candidate unit differs from source: " + unit)
            else:
                print("INSTALLED_UNIT_PARITY=PASS:" + unit)
        except OSError:
            failures.append("Cannot read candidate unit: " + unit)
        status = cmd(["/usr/bin/systemctl", "is-active", unit])
        if status.stdout.strip() != "inactive":
            failures.append("Candidate unit not inactive: " + unit)
    for unit in ("hermes-agency.service", "hermes-signed-broker.service",
                 "hermes-operator-sidecar.service"):
        status = cmd(["/usr/bin/systemctl", "is-active", unit])
        if status.stdout.strip() != "active":
            failures.append("Production service not active: " + unit)
    if not Path("/run/hermes-operator/admission.freeze").exists():
        failures.append("Admission freeze missing")
    for item in failures:
        print("RELEASE_ALIGNMENT_BLOCKER=" + item)
    print("RELEASE_ALIGNMENT=" + ("PASS" if not failures else "NO_GO"))
    print("CUTOVER_AUTHORIZED=NO")
    print("PRODUCTION_MUTATED=NO")
    return 0 if not failures else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo", default=str(ROOT))
    args = parser.parse_args(argv)
    return run(Path(args.repo))


if __name__ == "__main__":
    sys.exit(main())
