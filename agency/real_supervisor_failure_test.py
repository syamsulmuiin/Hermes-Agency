"""Opt-in real supervisor SIGKILL test; isolated systemd and SQLite only."""
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
import tempfile
import time

from .broker_grants import _canonical
from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import register_before_launch
from .real_systemd_auto_recovery_test import ctl
from .real_systemd_crash_acceptance import active, await_active, launch
from .fenced_systemd_supervisor import stop_and_verify_unit
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint


def sidecar(conn, control, database, key, uid, broker_end, supervisor_end):
    broker_end.close()
    supervisor_end.close()
    from .trusted_lease_ipc import serve_fence_connection
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)

    def cleanup(_claims):
        control.sendall(b"stop\n")
        if control.recv(16) != b"verified\n":
            raise PermissionError("Supervisor failed before verification")

    try:
        serve_fence_connection(conn, database, key, cleanup_before_release=cleanup)
    finally:
        conn.close()
        control.close()


def supervisor(control, broker_end, sidecar_end, peer_end, stop_received):
    broker_end.close()
    sidecar_end.close()
    peer_end.close()
    try:
        if control.recv(16) != b"stop\n":
            raise PermissionError("Unexpected supervisor request")
        with open(stop_received, "x", encoding="ascii") as out:
            out.write("stop-requested")
        while True:
            time.sleep(1)
    finally:
        control.close()


def wait_until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.05)
    return False


def denied(journal):
    try:
        require_recovered(journal)
    except PermissionError:
        return True
    return False


def verified(journal, unit):
    with sqlite3.connect(journal) as db:
        return db.execute("SELECT state FROM owned_units WHERE unit=?", (unit,)).fetchone() == ("verified",)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    uid = pwd.getpwnam("nobody").pw_uid
    if uid == 0:
        raise PermissionError("Non-root identity required")
    ident = secrets.token_hex(8)
    watcher = "hermes-real-supervisor-watch-" + ident + ".service"
    recovery = "hermes-real-supervisor-recover-" + ident + ".service"
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-supervisor-crash-", dir="/run") as folder:
        os.chmod(folder, 0o711)
        journal = folder + "/owned.sqlite"
        database = folder + "/trusted.sqlite"
        pidfile = folder + "/supervisor.pid"
        ready = folder + "/watch.ready"
        stop_received = folder + "/stop.received"
        worker = folder + "/watch.py"
        recover = folder + "/recover.py"
        repo = os.path.dirname(os.path.dirname(__file__))
        python = os.path.realpath(__import__("sys").executable)
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
        with open(worker, "w", encoding="utf-8") as out:
            out.write("import os,sys,time\n"
                      "open(" + repr(ready) + ",'x').write('ready')\n"
                      "while not os.path.isfile(" + repr(pidfile) + "): time.sleep(.05)\n"
                      "pid=int(open(" + repr(pidfile) + ").read())\n"
                      "while True:\n"
                      " try:\n"
                      "  state=open('/proc/%d/stat'%pid).read().split(') ',1)[1].split()[0]\n"
                      "  if state in ('Z','X'): sys.exit(1)\n"
                      " except FileNotFoundError: sys.exit(1)\n"
                      " time.sleep(.05)\n")
        with open(recover, "w", encoding="utf-8") as out:
            out.write("import sys\nsys.path.insert(0," + repr(repo) + ")\n"
                      "from agency.fenced_unit_journal import recover_owned_units\n"
                      "recover_owned_units(" + repr(journal) + ")\n")
        wp = "/run/systemd/system/" + watcher
        rp = "/run/systemd/system/" + recovery
        parent, peer = socket.socketpair()
        root_control, trusted_control = socket.socketpair()
        trusted = mp.Process(target=sidecar, args=(peer, trusted_control, database, key, uid, parent, root_control))
        root = mp.Process(target=supervisor, args=(root_control, parent, trusted_control, peer, stop_received))
        started = None
        try:
            for path, body in (
                (wp, "[Unit]\nDescription=Isolated supervisor PID watch\nOnFailure=" + recovery +
                     "\n[Service]\nType=simple\nRestart=no\nExecStart=" + python + " " + worker + "\n"),
                (rp, "[Unit]\nDescription=Isolated supervisor recovery\n[Service]\n"
                     "Type=oneshot\nExecStart=" + python + " " + recover + "\n")):
                with open(path, "x", encoding="utf-8") as out:
                    out.write(body)
                os.chmod(path, 0o600)
            if ctl("daemon-reload").returncode:
                raise RuntimeError("systemd reload failed")
            register_before_launch(journal, unit)
            launch(unit)
            await_active(unit)
            if ctl("start", watcher).returncode:
                raise RuntimeError("Watcher failed to start")
            if not wait_until(lambda: os.path.isfile(ready), 10):
                raise RuntimeError("Watcher not ready")
            root.start()
            with open(pidfile, "x", encoding="ascii") as out:
                out.write(str(root.pid))
            trusted.start()
            peer.close()
            trusted_control.close()
            root_control.close()
            from .trusted_lease_ipc import _send, _read_line
            parent.settimeout(8)
            _send(parent, {"grant": grant})
            if json.loads(_read_line(parent)) != {"status": "locked", "grant_id": claims["id"]}:
                raise AssertionError("Trusted lease not acquired")
            parent.close()
            if not wait_until(lambda: os.path.isfile(stop_received), 5):
                raise AssertionError("Root supervisor did not receive cleanup")
            with sqlite3.connect(database, timeout=.05, isolation_level=None) as db:
                try:
                    db.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    pass
                else:
                    db.rollback()
                    raise AssertionError("Sidecar unlocked before supervisor verification")
            if not denied(journal):
                raise AssertionError("Pending journal did not block startup")
            print("real_supervisor_sigkill_pending_gate_before_crash=PASS", flush=True)
            started = time.monotonic()
            root.kill()
            root.join(3)
            if root.exitcode is None:
                raise AssertionError("Root supervisor survived SIGKILL")
            if not denied(journal):
                raise AssertionError("Pending journal bypassed after supervisor death")
            print("real_supervisor_sigkill_pending_gate_after_crash=PASS", flush=True)
            if not wait_until(lambda: not trusted.is_alive(), 5):
                raise AssertionError("Sidecar did not terminate after failed cleanup")
            with sqlite3.connect(database, timeout=.2, isolation_level=None) as db:
                db.execute("BEGIN IMMEDIATE")
                db.rollback()
            print("real_supervisor_sigkill_sqlite_unlock_delay_ms=" +
                  str(round((time.monotonic() - started) * 1000)), flush=True)
            if not wait_until(lambda: not active(unit) and verified(journal, unit), 15):
                for name in (watcher, recovery, unit):
                    result = ctl("show", name, "--property=ActiveState,SubState,Result,ExecMainStatus")
                    print("diagnostic_" + name + "=" + result.stdout.decode(errors="replace"), flush=True)
                raise AssertionError("Independent recovery failed")
            require_recovered(journal)
            print("real_supervisor_sigkill_recovery_delay_ms=" +
                  str(round((time.monotonic() - started) * 1000)), flush=True)
            print("real_supervisor_sigkill_independent_recovery=PASS", flush=True)
        finally:
            parent.close()
            peer.close()
            root_control.close()
            trusted_control.close()
            for process in (root, trusted):
                if process.is_alive():
                    process.kill()
                if process.pid is not None:
                    process.join(3)
            ctl("stop", watcher)
            ctl("stop", recovery)
            if active(unit):
                stop_and_verify_unit(unit)
            for path in (wp, rp):
                if os.path.exists(path):
                    os.unlink(path)
            ctl("daemon-reload")
            ctl("reset-failed", watcher, recovery)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__ == "__main__":
    main()
