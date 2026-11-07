"""Single opt-in isolated systemd cutover and crash acceptance runner.

Runs existing real-systemd tests against their own staging fixtures.
Does not touch production units, production ledger, or broker socket.
"""
import argparse
import os
import subprocess
import sys
import time

CASES = (
    ("cutover", "agency.isolated_systemd_cutover_test",
     ("ISOLATED_SYSTEMD_CUTOVER_E2E=PASS",)),
    ("crash", "agency.real_integrated_crash_suite_test",
     ("INTEGRATED_ISOLATED_CRASH_SUITE=PASS",)),
)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    for label, module, markers in CASES:
        print("ACCEPTANCE_START=" + label, flush=True)
        result = subprocess.run(
            [sys.executable, "-m", module, "--execute"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=420, check=False)
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
        if result.stderr:
            print(result.stderr, file=sys.stderr, flush=True)
        if result.returncode or not set(markers).issubset(set(result.stdout.splitlines())):
            raise RuntimeError("Acceptance failed: " + label)
        print("ACCEPTANCE_PASS=" + label, flush=True)
    print("ISOLATED_SYSTEMD_AND_CRASH_ACCEPTANCE=PASS", flush=True)
    print("REAL_FENCED_BROKER_SOCKET_REPLAY_E2E=NOT_TESTED", flush=True)
    print("PRODUCTION_CUTOVER_GO=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.parse_args(argv)
    run()


if __name__ == "__main__":
    main()
