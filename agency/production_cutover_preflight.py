"""Read-only production cutover preflight.

This intentionally DOES NOT stop/start services, create journals, alter
admission state, or authorize cutover. It fails closed on stale deployments.
"""
import argparse
import os
import pathlib
import subprocess
import sys

EXPECTED_PIN = "912dce6aef6b"
SERVICES = ("hermes-agency.service", "hermes-signed-broker.service",
            "hermes-operator-sidecar.service")


def _systemctl(*args):
    result = subprocess.run(["/usr/bin/systemctl", *args],
                            capture_output=True, text=True, timeout=10,
                            check=False)
    if result.returncode:
        raise PermissionError("Unable to verify systemd state")
    return result.stdout.strip()


def preflight():
    problems = []
    for service in SERVICES:
        try:
            if _systemctl("is-active", service) != "active":
                problems.append("Production service not active: " + service)
        except (OSError, subprocess.TimeoutExpired, PermissionError):
            problems.append("Production service state unknown: " + service)

    # A sidecar running an earlier binary cannot participate in the
    # newly introduced admission lock. Its source checkout is not proof.
    problems.append("Live sidecar admission-lock capability not attested")
    problems.append("Race-free exclusive drain and inode stability not attested")
    problems.append("Production broker handover and rollback not acceptance-tested")

    candidate = pathlib.Path("/opt/hermes-fenced-" + EXPECTED_PIN)
    if not candidate.is_dir():
        problems.append("Pinned fenced candidate snapshot absent")

    for label, path in (
        ("ownership journal", "/var/lib/hermes-broker/owned-units.sqlite"),
        ("admission lock", "/run/hermes-admission/admission.lock"),
    ):
        if not os.path.isfile(path) or os.path.islink(path):
            problems.append(label + " not provisioned and verified")

    print("CUTOVER_PREFLIGHT=" + ("PASS" if not problems else "NO_GO"))
    for problem in problems:
        print("CUTOVER_BLOCKER=" + problem)
    print("PRODUCTION_MUTATED=NO")
    return 0 if not problems else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)
    return preflight()


if __name__ == "__main__":
    sys.exit(main())
