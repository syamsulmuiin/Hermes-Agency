"""Opt-in REAL systemd crash acceptance. Never installs or changes production units.

Run only on a disposable test VPS as root, with explicit --execute.
Uses one randomly named fenced unit, a private journal, and a test-only broker
child. The trusted-fence scenario is a socket EOF monitor, not real lease IPC.
"""
import argparse
import multiprocessing as mp
import os
import secrets
import signal
import socket
import subprocess
import tempfile
import time

from .fenced_systemd_supervisor import stop_and_verify_unit
from .fenced_unit_journal import register_before_launch, recover_owned_units


def ctl(*args):
    return subprocess.run(
        ["/usr/bin/systemctl", "--system", *args],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=10, check=False)


def state(unit):
    result = ctl("show", unit, "--property=ActiveState",
                 "--property=MainPID", "--property=Job")
    if result.returncode:
        raise RuntimeError("systemd state unavailable")
    return dict(line.split("=", 1) for line in result.stdout.decode(
        "ascii", "replace").splitlines() if "=" in line)


def active(unit):
    return state(unit).get("ActiveState") == "active"


def launch(unit):
    result = subprocess.run(
        ["/usr/bin/systemd-run", "--system", "--quiet",
         "--unit=" + unit, "--property=RuntimeMaxSec=60",
         "--property=Type=simple", "--", "/usr/bin/sleep", "45"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=10, check=False)
    if result.returncode:
        raise RuntimeError("test transient unit launch failed")


def broker(journal, unit, ready):
    register_before_launch(journal, unit)
    launch(unit)
    ready.set()
    while True:
        time.sleep(0.1)


def await_active(unit, timeout=5):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if active(unit):
            return
        time.sleep(0.05)
    raise RuntimeError("test unit not active")


def exercise():
    if os.geteuid() != 0:
        raise PermissionError("Root required")
    if not os.path.exists("/run/systemd/system"):
        raise RuntimeError("Systemd not available")
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-systemd-accept-", dir="/run") as directory:
        os.chmod(directory, 0o700)
        journal = os.path.join(directory, "owned.sqlite")
        ready = mp.Event()
        child = mp.Process(target=broker, args=(journal, unit, ready))
        child.start()
        try:
            if not ready.wait(10):
                raise RuntimeError("Test broker did not start")
            await_active(unit)
            os.kill(child.pid, signal.SIGKILL)
            child.join(5)
            if child.exitcode != -signal.SIGKILL:
                raise RuntimeError("Test broker SIGKILL not observed")
            if not active(unit):
                raise RuntimeError("Transient unit did not survive broker crash")
            # A new broker must not start while ownership remains pending.
            import sqlite3
            with sqlite3.connect(journal) as db:
                if db.execute("SELECT state FROM owned_units WHERE unit=?",
                              (unit,)).fetchone() != ("pending",):
                    raise RuntimeError("Pending ownership missing")
            # Simulate a startup recovery failure: the journal must remain pending.
            try:
                recover_owned_units(journal, stop_unit=lambda _: (
                    _ for _ in ()).throw(PermissionError("injected cleanup failure")))
            except PermissionError:
                pass
            else:
                raise RuntimeError("Injected failure unexpectedly succeeded")
            with sqlite3.connect(journal) as db:
                if db.execute("SELECT state FROM owned_units WHERE unit=?",
                              (unit,)).fetchone() != ("pending",):
                    raise RuntimeError("Failure did not preserve pending ownership")
            recovered = recover_owned_units(journal)
            if recovered != (unit,) or active(unit):
                raise RuntimeError("Independent systemd recovery failed")
            print("real_sigkill_recovery=PASS", flush=True)
            print("startup_pending_failure_gate=PASS (application gate only)", flush=True)

            # A separate live-fence EOF test: monitor closes connection then stops
            # its own unit. This is not trusted SQLite lease or sidecar wiring.
            second = "hermes-fenced-" + secrets.token_hex(16) + ".service"
            parent, peer = socket.socketpair()
            try:
                launch(second)
                await_active(second)
                peer.close()
                if parent.recv(1) != b"":
                    raise RuntimeError("Expected fence EOF")
                stop_and_verify_unit(second)
                if active(second):
                    raise RuntimeError("Unit still active after fence EOF")
                print("socket_fence_eof_cleanup=PASS (not trusted lease IPC)", flush=True)
            finally:
                parent.close()
                stop_and_verify_unit(second)
        finally:
            if child.is_alive():
                child.kill()
            child.join(5)
            stop_and_verify_unit(unit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Real systemd test requires explicit --execute")
    exercise()


if __name__ == "__main__":
    main()
