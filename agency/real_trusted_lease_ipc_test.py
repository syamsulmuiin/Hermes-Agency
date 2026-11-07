"""Isolated real trusted-UID lease IPC and systemd stop-before-unlock test.

Explicit --execute only. Uses a synthetic test-only signed grant and SQLite
fixture, a non-root sidecar, root supervisor and a random transient sleep unit.
Not a production deployment or crash-proof containment protocol.
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
import tempfile
import time

from .broker_grants import _canonical
from .real_systemd_crash_acceptance import active, await_active, launch
from .fenced_systemd_supervisor import stop_and_verify_unit
from .security import fingerprint


def sidecar(conn, control, database, key, uid, inherited_broker, inherited_supervisor):
    # fork inherits both ends of each socketpair. Close the broker and
    # supervisor endpoints in the child so broker close produces actual EOF.
    inherited_broker.close()
    inherited_supervisor.close()
    # Import before dropping privileges: /root is not traversable by nobody.
    # The child retains only preloaded Python code, not root filesystem access.
    from .trusted_lease_ipc import serve_fence_connection
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)

    def cleanup(_claims):
        # Trusted sidecar cannot control systemd. Ask the independent root
        # supervisor over a private inherited socket; await stop verification.
        control.sendall(b"stop\n")
        if control.recv(16) != b"verified\n":
            raise PermissionError("Root supervisor did not verify unit stop")

    try:
        serve_fence_connection(conn, database, key,
                               cleanup_before_release=cleanup)
    finally:
        conn.close()
        control.close()


def fixture(database, claims):
    with sqlite3.connect(database) as db:
        db.executescript("""
        CREATE TABLE tasks(id TEXT PRIMARY KEY,status TEXT,owner TEXT);
        CREATE TABLE task_leases(task_id TEXT PRIMARY KEY,worker TEXT,
            generation INTEGER,expires_at REAL);
        CREATE TABLE approvals(id TEXT PRIMARY KEY,status TEXT);
        CREATE TABLE execution_grants(idempotency_key TEXT,task_id TEXT,
            approval_id TEXT,worker TEXT,lease_generation INTEGER,
            action TEXT,params_hash TEXT);
        """)
        db.execute("INSERT INTO tasks VALUES (?,'in_progress','developer')",
                   (claims["task"],))
        db.execute("INSERT INTO task_leases VALUES (?,?,?,?)",
                   (claims["task"],claims["worker"],claims["lease_generation"],
                    time.time()+120))
        db.execute("INSERT INTO approvals VALUES (?,'consumed')",
                   (claims["approval"],))
        db.execute("INSERT INTO execution_grants VALUES (?,?,?,?,?,?,?)",
                   (claims["id"],claims["task"],claims["approval"],
                    claims["worker"],claims["lease_generation"],
                    "execute_shell",claims["params_hash"]))


def exercise():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Requires root and real systemd")
    nobody = pwd.getpwnam("nobody")
    uid = nobody.pw_uid
    if uid == 0:
        raise PermissionError("Non-root test identity required")
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-trusted-ipc-", dir="/run") as folder:
        os.chmod(folder, 0o700)
        # The trusted child needs directory traversal, but only this private
        # fixture DB is writable by it; no production trusted data is exposed.
        os.chmod(folder, 0o711)
        database = folder + "/trusted.sqlite"
        key = secrets.token_bytes(32)
        now = time.time()
        claims = {"v":1,"aud":"hermes-systemd-broker-v1",
                  "id":secrets.token_hex(32),"approval":"test-approval",
                  "task":"test-task","worker":"test-worker",
                  "lease_generation":1,"job":"noop",
                  "params_hash":fingerprint({"job":"noop"}),
                  "iat":now,"exp":now+60}
        # Test-only grant fixture; no real approval or production grant.
        envelope = {"claims":claims,"signature":
                    hmac.new(key,_canonical(claims),hashlib.sha256).hexdigest()}
        fixture(database,claims)
        os.chown(database,uid,uid)
        os.chmod(database,0o600)
        parent, peer = socket.socketpair()
        root_control, trusted_control = socket.socketpair()
        child = mp.Process(target=sidecar,args=(peer,trusted_control,database,key,uid,parent,root_control))
        try:
            launch(unit)
            await_active(unit)
            child.start()
            peer.close()
            trusted_control.close()
            from .trusted_lease_ipc import _send, _read_line
            parent.settimeout(8)
            _send(parent,{"grant":envelope})
            response = json.loads(_read_line(parent))
            if response != {"status":"locked","grant_id":claims["id"]}:
                raise AssertionError("Trusted sidecar did not lock lease")
            contender = sqlite3.connect(database,timeout=0.2,isolation_level=None)
            try:
                try:
                    contender.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    print("trusted_sqlite_lock_held_during_job=PASS",flush=True)
                else:
                    contender.rollback()
                    raise AssertionError("Contender acquired lock while job active")
            finally:
                contender.close()
            # Simulate broker crash: close IPC without DONE while unit is active.
            parent.close()
            root_control.settimeout(8)
            if root_control.recv(16) != b"stop\n":
                raise AssertionError("Sidecar did not request stop on broker EOF")
            contender = sqlite3.connect(database,timeout=0.2,isolation_level=None)
            try:
                try:
                    contender.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    print("trusted_lock_held_until_stop_verified=PASS",flush=True)
                else:
                    contender.rollback()
                    raise AssertionError("Lease unlocked before stop verification")
            finally:
                contender.close()
            stop_and_verify_unit(unit)
            if active(unit):
                raise AssertionError("Unit still active after stop")
            root_control.sendall(b"verified\n")
            child.join(8)
            if child.exitcode != 0:
                raise AssertionError("Trusted sidecar did not exit cleanly")
            with sqlite3.connect(database,timeout=2,isolation_level=None) as db:
                db.execute("BEGIN IMMEDIATE")
                db.rollback()
            print("trusted_uid_ipc_systemd_stop_before_unlock=PASS",flush=True)
        finally:
            parent.close()
            root_control.close()
            if child.is_alive():
                child.kill()
            child.join(3)
            if active(unit):
                stop_and_verify_unit(unit)


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    exercise()


if __name__=="__main__":
    main()
