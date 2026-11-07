"""Isolated SIGKILL crash exercise: real child process, fake systemd backend.

No systemctl/systemd-run calls, production sockets, grants or services.
This tests durable ownership and startup gating, NOT real systemd cleanup.
"""
import multiprocessing
import os
import signal
import sqlite3
import tempfile
import time

from .fenced_unit_journal import register_before_launch, recover_owned_units

UNIT = "hermes-fenced-" + "b" * 32 + ".service"


def _broker_child(journal, ready):
    register_before_launch(journal, UNIT)
    ready.set()
    while True:
        time.sleep(0.1)


def isolated_crash_exercise():
    if os.geteuid() != 0:
        raise PermissionError("Run in isolated root-owned test environment")
    with tempfile.TemporaryDirectory(prefix="hermes-crash-test-", dir="/run") as directory:
        os.chmod(directory, 0o700)
        journal = os.path.join(directory, "ownership.sqlite")
        ready = multiprocessing.Event()
        child = multiprocessing.Process(target=_broker_child, args=(journal, ready))
        child.start()
        try:
            if not ready.wait(5):
                raise RuntimeError("Broker test child failed to register")
            with sqlite3.connect(journal) as db:
                assert db.execute("SELECT state FROM owned_units WHERE unit=?",
                                  (UNIT,)).fetchone() == ("pending",)
            os.kill(child.pid, signal.SIGKILL)
            child.join(5)
            if child.is_alive() or child.exitcode != -signal.SIGKILL:
                raise RuntimeError("SIGKILL test did not terminate child")
            # Fake unit stays active until independent recovery stops it.
            active = {UNIT}
            def stop(unit):
                if unit not in active:
                    raise PermissionError("Unknown test unit")
                active.remove(unit)
            def startup_allowed():
                with sqlite3.connect(journal) as db:
                    return not db.execute(
                        "SELECT 1 FROM owned_units WHERE state='pending' LIMIT 1"
                    ).fetchone() and not active
            if startup_allowed():
                raise AssertionError("Startup allowed before recovery")
            recovered = recover_owned_units(journal, stop_unit=stop)
            if recovered != (UNIT,) or active or not startup_allowed():
                raise AssertionError("Recovery did not establish clean startup")
            return True
        finally:
            if child.is_alive():
                child.kill()
            child.join(5)


if __name__ == "__main__":
    print("isolated_sigkill_recovery=" + str(isolated_crash_exercise()))
