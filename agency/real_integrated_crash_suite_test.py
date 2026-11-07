"""One-command opt-in isolated crash-containment acceptance suite.

Runs real systemd / trusted-UID IPC scenarios sequentially, stopping on failure.
Does not modify or restart production service, database, or grants.
"""
import argparse
import os
import subprocess
import sys
import time

SCENARIOS = (
    ("trusted_ipc", "agency.real_trusted_lease_ipc_test",
     ("trusted_sqlite_lock_held_during_job=PASS",
      "trusted_lock_held_until_stop_verified=PASS",
      "trusted_uid_ipc_systemd_stop_before_unlock=PASS")),
    ("sidecar_sigkill", "agency.real_sidecar_sigkill_recovery_test",
     ("real_sidecar_sigkill_pending_gate=PASS",
      "real_sidecar_sigkill_independent_recovery=PASS")),
    ("supervisor_sigkill", "agency.real_supervisor_failure_test",
     ("real_supervisor_sigkill_pending_gate_before_crash=PASS",
      "real_supervisor_sigkill_pending_gate_after_crash=PASS",
      "real_supervisor_sigkill_independent_recovery=PASS")),
    ("cleanup_restart", "agency.real_cleanup_restart_gate_test",
     ("real_cleanup_failure_lock_held_before_injection=PASS",
      "real_cleanup_failure_pending_gate=PASS",
      "real_restart_pending_systemd_gate=PASS",
      "real_restart_after_verified_recovery=PASS")),
)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    if not os.path.isfile("/usr/bin/systemctl"):
        raise PermissionError("systemctl unavailable")
    failures = []
    for name, module, expected in SCENARIOS:
        print("SCENARIO_START=" + name, flush=True)
        started = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, "-m", module, "--execute"],
                cwd=os.path.dirname(os.path.dirname(__file__)),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=90, check=False)
        except subprocess.TimeoutExpired:
            print("SCENARIO_TIMEOUT=" + name, flush=True)
            failures.append(name)
            break
        output = result.stdout.decode("utf-8", "replace")
        error = result.stderr.decode("utf-8", "replace")
        if output:
            print(output, end="" if output.endswith("\n") else "\n", flush=True)
        if error:
            print(error, end="" if error.endswith("\n") else "\n", file=sys.stderr, flush=True)
        lines = set(output.splitlines())
        missing = [marker for marker in expected if marker not in lines]
        if result.returncode != 0 or missing:
            print("SCENARIO_FAILED=" + name + " exit=" + str(result.returncode)
                  + " missing=" + repr(missing), flush=True)
            failures.append(name)
            break
        print("SCENARIO_PASS=" + name + " elapsed_ms=" +
              str(round((time.monotonic() - started) * 1000)), flush=True)
    if failures:
        raise RuntimeError("Acceptance suite failed: " + ",".join(failures))
    print("INTEGRATED_ISOLATED_CRASH_SUITE=PASS", flush=True)
    print("PRODUCTION_INTEGRATION_VERIFIED=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__ == "__main__":
    main()
