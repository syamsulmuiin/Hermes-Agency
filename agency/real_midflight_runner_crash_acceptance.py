"""Real mid-flight systemd-run SIGKILL acceptance, isolated from production.

Uses the actual fenced runner code with a test-only allowlisted sleep override
in a forked child. The production allowlist and service units are untouched.
"""
import argparse
import os
import secrets
import select
import signal
import socket
import sqlite3
import tempfile
import time

from .fenced_staging_serialization import staging_launch, staging_recover
from .fenced_startup_gate import require_recovered
from .fenced_systemd_supervisor import run_fenced_systemd_unit, stop_and_verify_unit
from .fenced_unit_journal import _connect
from .real_systemd_crash_acceptance import active, await_active


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and systemd required")
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-midflight-", dir="/run") as folder:
        os.chmod(folder, 0o700)
        journal = os.path.join(folder, "owned.sqlite")
        with _connect(journal):
            pass
        ready_read, ready_write = os.pipe()
        parent, child_fence = socket.socketpair()
        pid = os.fork()
        if pid == 0:
            os.close(ready_read)
            parent.close()
            try:
                # Change the in-memory test child only, not source or production.
                from . import systemd_jobs
                systemd_jobs.JOBS["noop"] = ("/usr/bin/sleep", "6")
                def execute():
                    os.write(ready_write, b"R")
                    return run_fenced_systemd_unit("noop", child_fence, unit)
                staging_launch(journal, unit, execute)
                os._exit(0)
            except BaseException:
                os._exit(3)
        os.close(ready_write)
        child_fence.close()
        try:
            readable, _, _ = select.select([ready_read], [], [], 10)
            if not readable or os.read(ready_read, 1) != b"R":
                raise AssertionError("Runner never reached launch boundary")
            await_active(unit, timeout=5)
            with sqlite3.connect(journal) as db:
                if db.execute("SELECT state FROM owned_units WHERE unit=?",
                              (unit,)).fetchone() != ("pending",):
                    raise AssertionError("Pending ownership absent")
            os.kill(pid, signal.SIGKILL)
            _, status = os.waitpid(pid, 0)
            pid = None
            if os.waitstatus_to_exitcode(status) != -signal.SIGKILL:
                raise AssertionError("Broker SIGKILL not observed")
            if not active(unit):
                raise AssertionError("Real runner transient did not survive broker death")
            try:
                require_recovered(journal)
            except PermissionError:
                pass
            else:
                raise AssertionError("Gate accepted unfinished runner")
            print("REAL_RUNNER_MIDFLIGHT_SIGKILL_GATE=PASS", flush=True)
            staging_recover(journal)
            require_recovered(journal)
            if active(unit):
                raise AssertionError("Recovery left real runner unit active")
            print("REAL_RUNNER_MIDFLIGHT_RECOVERY=PASS", flush=True)
            print("REAL_RUNNER_MIDFLIGHT_RESTART_GATE=PASS", flush=True)
        finally:
            os.close(ready_read)
            parent.close()
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
            stop_and_verify_unit(unit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__ == "__main__":
    main()
