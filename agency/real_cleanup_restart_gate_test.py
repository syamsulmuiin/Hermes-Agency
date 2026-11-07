"""Opt-in real IPC cleanup-failure and journal-gated service restart tests.

Private SQLite and random transient systemd units only. No production wiring.
"""
import argparse
import hashlib
import hmac
import json
import multiprocessing as mp
import os
import pwd
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

from .broker_grants import _canonical
from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import register_before_launch, recover_owned_units
from .real_systemd_auto_recovery_test import ctl
from .real_systemd_crash_acceptance import active, await_active, launch
from .fenced_systemd_supervisor import stop_and_verify_unit
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint


def fail_sidecar(conn, database, key, uid, inherited_parent):
    inherited_parent.close()
    from .trusted_lease_ipc import serve_fence_connection
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)

    def fail_cleanup(_claims):
        raise PermissionError("Injected independent cleanup failure")

    serve_fence_connection(conn, database, key, cleanup_before_release=fail_cleanup)


def wait_until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.05)
    return False


def state(journal, unit):
    with sqlite3.connect(journal) as db:
        return db.execute("SELECT state FROM owned_units WHERE unit=?", (unit,)).fetchone()


def gated_restart(journal, unit, directory):
    """Use a real systemd unit with ExecStartPre startup gate, not a Python mock."""
    name = "hermes-restart-gate-" + secrets.token_hex(8) + ".service"
    path = "/run/systemd/system/" + name
    repo = os.path.dirname(os.path.dirname(__file__))
    python = sys.executable
    marker = directory + "/started"
    script = directory + "/startup.py"
    with open(script, "x", encoding="utf-8") as out:
        out.write("import sys\nsys.path.insert(0," + repr(repo) + ")\n"
                  "from agency.fenced_startup_gate import require_recovered\n"
                  "require_recovered(" + repr(journal) + ")\n")
    body = ("[Unit]\nDescription=Isolated journal-gated restart test\n"
            "[Service]\nType=oneshot\n"
            "ExecStartPre=" + python + " " + script + "\n"
            "ExecStart=/usr/bin/touch " + marker + "\n")
    try:
        with open(path, "x", encoding="utf-8") as out:
            out.write(body)
        os.chmod(path, 0o600)
        if ctl("daemon-reload").returncode:
            raise RuntimeError("systemd reload failed")
        result = ctl("start", name)
        if result.returncode == 0 or os.path.exists(marker):
            raise AssertionError("Pending journal allowed service startup")
        if state(journal, unit) != ("pending",):
            raise AssertionError("Journal changed during rejected startup")
        print("real_restart_pending_systemd_gate=PASS", flush=True)
        recover_owned_units(journal)
        if active(unit) or state(journal, unit) != ("verified",):
            raise AssertionError("Recovery failed to verify stopped job")
        require_recovered(journal)
        ctl("reset-failed", name)
        if ctl("start", name).returncode or not os.path.isfile(marker):
            raise AssertionError("Verified journal did not allow service startup")
        print("real_restart_after_verified_recovery=PASS", flush=True)
    finally:
        ctl("stop", name)
        if os.path.exists(path):
            os.unlink(path)
        ctl("daemon-reload")
        ctl("reset-failed", name)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    uid = pwd.getpwnam("nobody").pw_uid
    if uid == 0:
        raise PermissionError("Non-root identity required")
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-cleanup-restart-", dir="/run") as folder:
        os.chmod(folder, 0o711)
        journal = folder + "/owned.sqlite"
        database = folder + "/trusted.sqlite"
        key = secrets.token_bytes(32)
        now = time.time()
        claims = {"v": 1, "aud": "hermes-systemd-broker-v1",
                  "id": secrets.token_hex(32), "approval": "test-approval",
                  "task": "test-task", "worker": "test-worker",
                  "lease_generation": 1, "job": "noop",
                  "params_hash": fingerprint({"job": "noop"}),
                  "iat": now, "exp": now + 60}
        grant = {"claims": claims, "signature":
                 hmac.new(key, _canonical(claims), hashlib.sha256).hexdigest()}
        fixture(database, claims)
        os.chown(database, uid, uid)
        os.chmod(database, 0o600)
        parent, peer = socket.socketpair()
        child = mp.Process(target=fail_sidecar, args=(peer, database, key, uid, parent))
        try:
            register_before_launch(journal, unit)
            launch(unit)
            await_active(unit)
            child.start()
            peer.close()
            from .trusted_lease_ipc import _send, _read_line
            parent.settimeout(8)
            _send(parent, {"grant": grant})
            if json.loads(_read_line(parent)) != {"status": "locked", "grant_id": claims["id"]}:
                raise AssertionError("Trusted sidecar did not acquire lease")
            with sqlite3.connect(database, timeout=.1, isolation_level=None) as db:
                try:
                    db.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    print("real_cleanup_failure_lock_held_before_injection=PASS", flush=True)
                else:
                    db.rollback()
                    raise AssertionError("Lease not held before cleanup failure")
            parent.close()
            child.join(5)
            if child.exitcode is None or child.exitcode == 0:
                raise AssertionError("Injected cleanup did not fail")
            with sqlite3.connect(database, timeout=1, isolation_level=None) as db:
                db.execute("BEGIN IMMEDIATE")
                db.rollback()
            if not active(unit) or state(journal, unit) != ("pending",):
                raise AssertionError("Failed cleanup lost pending ownership")
            try:
                require_recovered(journal)
            except PermissionError:
                print("real_cleanup_failure_pending_gate=PASS", flush=True)
            else:
                raise AssertionError("Failed cleanup bypassed startup gate")
            gated_restart(journal, unit, folder)
        finally:
            parent.close()
            peer.close()
            if child.is_alive():
                child.kill()
            if child.pid is not None:
                child.join(3)
            if active(unit):
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
