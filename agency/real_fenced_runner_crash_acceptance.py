"""Isolated real-runner and SIGKILL lifecycle acceptance; no production units.

Exercises the actual allowlisted systemd-run backend, and a real transient
hold unit to test broker death, failed stop, gate denial, and recovery.
"""
import argparse
import os
import secrets
import signal
import socket
import sqlite3
import subprocess
import time
import tempfile

from .fenced_systemd_supervisor import (
    run_fenced_systemd_unit, stop_and_verify_unit, _verified_stopped_state)
from .fenced_staging_serialization import staging_launch, staging_recover
from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import _connect
from .real_systemd_crash_acceptance import launch, await_active, active


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and systemd required")
    with tempfile.TemporaryDirectory(prefix="hermes-real-runner-", dir="/run") as folder:
        os.chmod(folder, 0o700)
        journal = os.path.join(folder, "owned.sqlite")
        with _connect(journal):
            pass
        # The exact production-candidate fixed-job runner, not a test stub.
        left, right = socket.socketpair()
        try:
            unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
            result = staging_launch(journal, unit,
                                    lambda: run_fenced_systemd_unit(
                                        "noop", left, unit))
            if result.get("exit_code") != 0:
                raise AssertionError("Real runner returned nonzero")
            staging_recover(journal)
            require_recovered(journal)
            print("REAL_FENCED_SYSTEMD_RUNNER=PASS", flush=True)
        finally:
            left.close()
            right.close()

        # A short allowlisted job cannot reliably be SIGKILLed mid-flight.
        # Use a real, separate test-only sleep transient unit for the crash
        # lifecycle. Never mislabel this as an actual runner mid-job crash.
        held = "hermes-fenced-" + secrets.token_hex(16) + ".service"
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            try:
                staging_launch(journal, held, lambda: (
                    launch(held), await_active(held),
                    os.write(write_fd, b"ready")))
                while True:
                    time.sleep(0.1)
            except BaseException:
                os._exit(2)
        os.close(write_fd)
        try:
            import select
            ready, _, _ = select.select([read_fd], [], [], 15)
            if not ready or os.read(read_fd, 5) != b"ready":
                raise AssertionError("Transient crash fixture not ready")
            os.kill(pid, signal.SIGKILL)
            _, status = os.waitpid(pid, 0)
            pid = None
            if os.waitstatus_to_exitcode(status) != -signal.SIGKILL:
                raise AssertionError("SIGKILL not observed")
            if not active(held):
                raise AssertionError("Transient unit did not survive SIGKILL")
            with sqlite3.connect(journal) as db:
                if db.execute("SELECT state FROM owned_units WHERE unit=?",
                              (held,)).fetchone() != ("pending",):
                    raise AssertionError("Missing pending ownership")
            try:
                require_recovered(journal)
            except PermissionError:
                pass
            else:
                raise AssertionError("Startup gate accepted pending unit")
            print("REAL_SIGKILL_PENDING_GATE=PASS", flush=True)
            try:
                staging_recover(journal, stop_unit=lambda _: (
                    _ for _ in ()).throw(PermissionError("Injected stop failure")))
            except PermissionError:
                pass
            else:
                raise AssertionError("Failed stop unexpectedly succeeded")
            if not active(held):
                raise AssertionError("Injected failure stopped the unit")
            with sqlite3.connect(journal) as db:
                if db.execute("SELECT state FROM owned_units WHERE unit=?",
                              (held,)).fetchone() != ("pending",):
                    raise AssertionError("Stop failure lost pending record")
            print("REAL_STOP_FAILURE_PRESERVES_PENDING=PASS", flush=True)
            staging_recover(journal)
            require_recovered(journal)
            if active(held) or not _verified_stopped_state(held):
                raise AssertionError("Recovery failed to verify stop")
            print("REAL_SIGKILL_RECOVERY_VERIFIED=PASS", flush=True)
            next_unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
            staging_launch(journal, next_unit, lambda: None)
            staging_recover(journal)
            require_recovered(journal)
            print("REAL_RESTART_AFTER_RECOVERY=PASS", flush=True)
        finally:
            os.close(read_fd)
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
            # Always attempt cleanup of our exact random transient unit.
            stop_and_verify_unit(held)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__ == "__main__":
    main()
