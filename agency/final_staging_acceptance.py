"""Single-command development/staging acceptance; never changes production units.

Explicit --execute is required because isolated acceptance tests create temporary
systemd units under /run. This suite does NOT certify production broker wiring.
"""
import argparse
import os
import subprocess
import sys

SCENARIOS = (
    ("unit", (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"),
     ("OK",)),
    ("integrated_crash", (sys.executable, "-m", "agency.real_integrated_crash_suite_test", "--execute"),
     ("INTEGRATED_ISOLATED_CRASH_SUITE=PASS",)),
    ("staging_race", (sys.executable, "-m", "agency.real_staging_race_acceptance_test", "--execute"),
     ("RACE_POST_RECOVERY_GATE=PASS",)),
    ("integrated_staging", (sys.executable, "-m", "agency.real_integrated_staging_crash_test", "--execute"),
     ("INTEGRATED_INDEPENDENT_RECOVERY_AND_GATE=PASS",)),
)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    root = os.path.dirname(os.path.dirname(__file__))
    for name, command, markers in SCENARIOS:
        print("ACCEPTANCE_START=" + name, flush=True)
        result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=240, check=False)
        output = result.stdout.decode("utf-8", "replace")
        error = result.stderr.decode("utf-8", "replace")
        print(output, end="" if output.endswith("\n") else "\n", flush=True)
        print(error, end="" if error.endswith("\n") else "\n",
              file=sys.stderr, flush=True)
        combined = output + "\n" + error
        if result.returncode or any(marker not in combined for marker in markers):
            raise RuntimeError("Acceptance failed: " + name +
                               " exit=" + str(result.returncode))
        print("ACCEPTANCE_PASS=" + name, flush=True)
    for service in ("hermes-agency.service", "hermes-signed-broker.service"):
        status = subprocess.run(("/usr/bin/systemctl", "is-active", service),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=10, check=False)
        if status.returncode or status.stdout.strip() != b"active":
            raise RuntimeError("Production service not active: " + service)
        print("PRODUCTION_UNCHANGED_ACTIVE=" + service, flush=True)
    print("STAGING_ACCEPTANCE=PASS", flush=True)
    print("PRODUCTION_FENCED_INTEGRATION_VERIFIED=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__ == "__main__":
    main()
