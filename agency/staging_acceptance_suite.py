"""Opt-in isolated acceptance runner for staging fencing components.

This suite distinguishes component crash evidence from actual launcher wiring.
It never uses production credentials, grants, databases, or service units.
"""
import argparse
import os
import subprocess
import sys
import time

SCENARIOS = (
    ("trusted_stop_before_unlock", "agency.real_trusted_lease_ipc_test",
     "trusted_uid_ipc_systemd_stop_before_unlock=PASS"),
    ("broker_sigkill_independent_recovery", "agency.real_sidecar_sigkill_recovery_test",
     "real_sidecar_sigkill_independent_recovery=PASS"),
    ("supervisor_sigkill_independent_recovery", "agency.real_supervisor_failure_test",
     "real_supervisor_sigkill_independent_recovery=PASS"),
    ("restart_gate", "agency.real_cleanup_restart_gate_test",
     "real_restart_after_verified_recovery=PASS"),
)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Isolated acceptance requires root and real systemd")
    for name, module, marker in SCENARIOS:
        print("STAGING_ACCEPTANCE_START=" + name, flush=True)
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-m", module, "--execute"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=90, check=False)
        output = result.stdout.decode("utf-8", "replace")
        if output:
            print(output, end="" if output.endswith("\n") else "\n", flush=True)
        if result.returncode != 0 or marker not in output.splitlines():
            error = result.stderr.decode("utf-8", "replace")
            if error:
                print(error, file=sys.stderr, flush=True)
            raise RuntimeError("Isolated acceptance failed: " + name)
        print("STAGING_ACCEPTANCE_PASS=" + name + " elapsed_ms=" +
              str(round((time.monotonic() - started) * 1000)), flush=True)
    print("ISOLATED_STAGING_COMPONENT_ACCEPTANCE=PASS", flush=True)
    print("NEW_LAUNCHER_REAL_END_TO_END_VERIFIED=NO", flush=True)
    print("CONCURRENT_LAUNCH_RECOVERY_VERIFIED=NO", flush=True)
    print("DIRECT_SYSTEMD_BYPASS_CLOSED=NO", flush=True)
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
