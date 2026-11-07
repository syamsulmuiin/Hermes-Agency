"""Four isolated systemd crash-containment acceptance scenarios.

Opt-in root-only test; private ownership journals, random units and no
production services. Systemd OnFailure is the independent recovery authority.
"""
import argparse
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time

from .fenced_unit_journal import register_before_launch
from .fenced_startup_gate import require_recovered
from .fenced_systemd_supervisor import stop_and_verify_unit
from .real_systemd_crash_acceptance import active, launch


def ctl(*args):
    return subprocess.run(("/usr/bin/systemctl", "--system", *args),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          stdin=subprocess.DEVNULL, timeout=15, check=False)


def wait_until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def pending(journal):
    with sqlite3.connect(journal) as db:
        return db.execute(
            "SELECT COUNT(*) FROM owned_units WHERE state='pending'").fetchone()[0]


def exercise_case(case):
    ident = secrets.token_hex(8)
    watched = "hermes-crash-watch-" + ident + ".service"
    recovery = "hermes-crash-recover-" + ident + ".service"
    job = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-crash-matrix-", dir="/run") as folder:
        os.chmod(folder, 0o700)
        journal = folder + "/owned.sqlite"
        ready = folder + "/ready"
        worker = folder + "/worker.py"
        recover = folder + "/recover.py"
        repo = os.path.dirname(os.path.dirname(__file__))
        python = sys.executable
        with open(worker, "w", encoding="utf-8") as out:
            out.write("import sys,time\nsys.path.insert(0," + repr(repo) + ")\n"
                      "from agency.fenced_unit_journal import register_before_launch\n"
                      "from agency.real_systemd_crash_acceptance import launch\n"
                      "register_before_launch(" + repr(journal) + "," + repr(job) + ")\n"
                      "launch(" + repr(job) + ")\n"
                      "open(" + repr(ready) + ",'x').write('ready')\n"
                      "while True: time.sleep(1)\n")
        with open(recover, "w", encoding="utf-8") as out:
            out.write("import sys\nsys.path.insert(0," + repr(repo) + ")\n"
                      "from agency.fenced_unit_journal import recover_owned_units\n"
                      "recover_owned_units(" + repr(journal) + ")\n")
        wp = "/run/systemd/system/" + watched
        rp = "/run/systemd/system/" + recovery
        # A dedicated systemd-managed recovery unit outlives the watched
        # process. For the supervisor-crash case, this recovery unit is
        # separate from the deliberately killed supervisor.
        unit_text = ("[Unit]\nDescription=Isolated crash matrix watched process\n"
                     "OnFailure=" + recovery + "\n"
                     "[Service]\nType=simple\nRestart=no\n"
                     "ExecStart=" + python + " " + worker + "\n")
        recover_text = ("[Unit]\nDescription=Isolated crash matrix recovery\n"
                        "[Service]\nType=oneshot\n"
                        "ExecStart=" + python + " " + recover + "\n")
        try:
            for path, body in ((wp, unit_text), (rp, recover_text)):
                with open(path, "x", encoding="utf-8") as out:
                    out.write(body)
                os.chmod(path, 0o600)
            if ctl("daemon-reload").returncode:
                raise RuntimeError("systemd reload failed")
            if ctl("start", watched).returncode:
                raise RuntimeError("watched service start failed")
            if not wait_until(lambda: os.path.isfile(ready) and active(job)):
                raise RuntimeError("isolated job did not become active")
            try:
                require_recovered(journal)
            except PermissionError:
                pass
            else:
                raise AssertionError("Pending journal failed to block restart")
            if case == "cleanup_failure":
                # Simulate a failed cleanup operation without marking verified.
                def fail_stop(_unit):
                    raise PermissionError("Injected cleanup failure")
                from .fenced_unit_journal import recover_owned_units
                try:
                    recover_owned_units(journal, stop_unit=fail_stop)
                except PermissionError:
                    pass
                else:
                    raise AssertionError("Injected cleanup failure was ignored")
                if not active(job) or pending(journal) != 1:
                    raise AssertionError("Failed cleanup incorrectly cleared ownership")
                try:
                    require_recovered(journal)
                except PermissionError:
                    print("cleanup_failure_blocks_new_work=PASS", flush=True)
                else:
                    raise AssertionError("Failed cleanup allowed new work")
            elif case == "restart_gate":
                # Recheck startup gate after simulated restart while orphan is
                # still running, before independent recovery is permitted.
                try:
                    require_recovered(journal)
                except PermissionError:
                    print("restart_pending_journal_gate=PASS", flush=True)
                else:
                    raise AssertionError("Restart gate accepted pending ownership")
            if ctl("kill", "--signal=SIGKILL", "--kill-who=main", watched).returncode:
                raise RuntimeError("Failed to kill watched test process")
            if not wait_until(lambda: pending(journal) == 0 and not active(job)):
                raise AssertionError("Independent systemd recovery failed for " + case)
            require_recovered(journal)
            print(case + "_independent_recovery=PASS", flush=True)
        finally:
            ctl("stop", watched)
            ctl("stop", recovery)
            if active(job):
                stop_and_verify_unit(job)
            for path in (wp, rp):
                if os.path.exists(path):
                    os.unlink(path)
            ctl("daemon-reload")
            ctl("reset-failed", watched, recovery)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Requires root and real systemd")
    for case in ("sidecar_sigkill", "supervisor_sigkill",
                 "cleanup_failure", "restart_gate"):
        exercise_case(case)


if __name__ == "__main__":
    main()
