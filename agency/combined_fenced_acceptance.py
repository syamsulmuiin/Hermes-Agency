"""One-command combined safety acceptance, without changing active production.

This is a staging gate, NOT production cutover certification. Candidate socket
and systemd candidate service runtime acceptance must be added before claiming
a production-ready broker.
"""
import argparse
import os
import subprocess
import sys

SCENARIOS = (
    ("candidate_framing", (sys.executable, "-m", "unittest",
      "discover", "-s", "tests", "-p", "test_fenced_candidate_framing.py", "-q"), ("OK",)),
    ("candidate_socket", (sys.executable, "-m", "unittest",
      "discover", "-s", "tests", "-p", "test_fenced_candidate_socket.py", "-q"), ("OK",)),
    ("candidate_broker", (sys.executable, "-m", "unittest",
      "discover", "-s", "tests", "-p", "test_fenced_broker_candidate.py", "-q"), ("OK",)),
    ("candidate_recovery", (sys.executable, "-m", "unittest",
      "discover", "-s", "tests", "-p", "test_fenced_owned_recovery.py", "-q"), ("OK",)),
    ("candidate_preflight", (sys.executable, "-m",
      "agency.fenced_candidate_preflight"), ("FENCED_CANDIDATE_STATIC_PREFLIGHT=PASS",)),
    ("all_unit_tests", (sys.executable, "-m", "unittest", "discover",
      "-s", "tests", "-q"), ("OK",)),
    ("real_crash_suite", (sys.executable, "-m",
      "agency.real_integrated_crash_suite_test", "--execute"),
      ("INTEGRATED_ISOLATED_CRASH_SUITE=PASS",)),
    ("real_staging_race", (sys.executable, "-m",
      "agency.real_staging_race_acceptance_test", "--execute"),
      ("RACE_POST_RECOVERY_GATE=PASS",)),
    ("real_staging_broker_sigkill", (sys.executable, "-m",
      "agency.real_integrated_staging_crash_test", "--execute"),
      ("INTEGRATED_REAL_BROKER_SIGKILL_GATE=PASS",
       "INTEGRATED_WATCHDOG_ONFAILURE_TRIGGERED=PASS",
       "INTEGRATED_INDEPENDENT_RECOVERY_AND_GATE=PASS")),
)


def _run(command, root, timeout):
    try:
        return subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Acceptance scenario timed out: " + repr(command)) from exc


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    root = os.path.dirname(os.path.dirname(__file__))
    for name, command, markers in SCENARIOS:
        print("COMBINED_START=" + name, flush=True)
        result = _run(command, root, 240)
        output = result.stdout.decode("utf-8", "replace")
        error = result.stderr.decode("utf-8", "replace")
        if output:
            print(output, end="" if output.endswith("\n") else "\n", flush=True)
        if error:
            print(error, end="" if error.endswith("\n") else "\n",
                  file=sys.stderr, flush=True)
        if result.returncode or any(marker not in output + error for marker in markers):
            raise RuntimeError("COMBINED_FAILED=" + name +
                               " exit=" + str(result.returncode))
        print("COMBINED_PASS=" + name, flush=True)
    for name in ("hermes-agency.service", "hermes-signed-broker.service"):
        result = _run(("/usr/bin/systemctl", "is-active", name), root, 10)
        if result.returncode or result.stdout.strip() != b"active":
            raise RuntimeError("Production service inactive: " + name)
        print("PRODUCTION_STILL_ACTIVE=" + name, flush=True)
    print("COMBINED_STAGING_ACCEPTANCE=PASS", flush=True)
    print("PERSISTENT_CANDIDATE_END_TO_END_VERIFIED=NO", flush=True)
    print("PRODUCTION_CUTOVER_AUTHORIZED=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__ == "__main__":
    main()
