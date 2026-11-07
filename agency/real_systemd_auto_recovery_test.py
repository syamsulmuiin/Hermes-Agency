"""Opt-in isolated systemd OnFailure automatic crash recovery acceptance.

No production service files, grants, trusted DB, or broker configuration touched.
Test broker uses a private journal and one random transient sleep unit.
"""
import argparse
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time

from .fenced_systemd_supervisor import stop_and_verify_unit
from .fenced_unit_journal import register_before_launch
from .fenced_startup_gate import require_recovered
from .real_systemd_crash_acceptance import active, launch


def ctl(*args):
    return subprocess.run(["/usr/bin/systemctl", "--system", *args],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15, check=False)


def worker(journal, unit, ready):
    register_before_launch(journal, unit)
    launch(unit)
    with open(ready, "x", encoding="ascii") as out:
        out.write("ready\n")
    while True:
        time.sleep(1)


def exercise():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Requires root and real systemd")
    ident = secrets.token_hex(8)
    broker_name = "hermes-auto-test-broker-" + ident + ".service"
    recovery_name = "hermes-auto-test-recover-" + ident + ".service"
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-auto-test-", dir="/run") as directory:
        os.chmod(directory, 0o700)
        journal = directory + "/owned.sqlite"
        ready = directory + "/ready"
        repo = os.path.dirname(os.path.dirname(__file__))
        python = sys.executable
        broker_script = directory + "/broker.py"
        recovery_script = directory + "/recover.py"
        with open(broker_script, "w", encoding="utf-8") as out:
            out.write("import os,sys,time\nsys.path.insert(0," + repr(repo) +
                      ")\nfrom agency.real_systemd_auto_recovery_test import worker\n"
                      "worker(" + repr(journal) + "," + repr(unit) + "," + repr(ready) + ")\n")
        with open(recovery_script, "w", encoding="utf-8") as out:
            out.write("import sys\nsys.path.insert(0," + repr(repo) +
                      ")\nfrom agency.fenced_unit_journal import recover_owned_units\n"
                      "recover_owned_units(" + repr(journal) + ")\n")
        bp = "/run/systemd/system/" + broker_name
        rp = "/run/systemd/system/" + recovery_name
        broker_unit = ("[Unit]\nDescription=Isolated Hermes crash test broker\n"
                       "OnFailure=" + recovery_name + "\n"
                       "[Service]\nType=simple\nRestart=no\n"
                       "ExecStart=" + python + " " + broker_script + "\n")
        recovery_unit = ("[Unit]\nDescription=Isolated Hermes crash test recovery\n"
                         "[Service]\nType=oneshot\n"
                         "ExecStart=" + python + " " + recovery_script + "\n")
        if os.path.lexists(bp) or os.path.lexists(rp):
            raise RuntimeError("Test unit collision")
        try:
            for path, contents in ((bp, broker_unit), (rp, recovery_unit)):
                with open(path, "x", encoding="utf-8") as out:
                    out.write(contents)
                os.chmod(path, 0o600)
            if ctl("daemon-reload").returncode:
                raise RuntimeError("Test daemon reload failed")
            if ctl("start", broker_name).returncode:
                raise RuntimeError("Test broker failed to start")
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline and not os.path.isfile(ready):
                time.sleep(0.1)
            if not os.path.isfile(ready) or not active(unit):
                raise RuntimeError("Test broker did not launch transient unit")
            try:
                require_recovered(journal)
            except PermissionError:
                print("auto_recovery_pending_gate=PASS", flush=True)
            else:
                raise AssertionError("Pending journal did not block startup")
            if ctl("kill", "--signal=SIGKILL", "--kill-who=main", broker_name).returncode:
                raise RuntimeError("Failed to SIGKILL isolated test broker")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                with sqlite3.connect(journal) as db:
                    row = db.execute("SELECT state FROM owned_units WHERE unit=?",
                                     (unit,)).fetchone()
                if row == ("verified",) and not active(unit):
                    require_recovered(journal)
                    print("systemd_onfailure_automatic_recovery=PASS", flush=True)
                    return
                time.sleep(0.15)
            raise RuntimeError("OnFailure did not verify and stop orphaned test unit")
        finally:
            ctl("stop", broker_name)
            ctl("stop", recovery_name)
            if active(unit):
                stop_and_verify_unit(unit)
            for path in (bp, rp):
                if os.path.exists(path):
                    os.unlink(path)
            ctl("daemon-reload")
            ctl("reset-failed", broker_name, recovery_name)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Real systemd execution requires --execute")
    exercise()


if __name__ == "__main__":
    main()
