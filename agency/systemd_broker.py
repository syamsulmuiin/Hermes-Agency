"""Experimental operator-only broker for fixed systemd diagnostic jobs.

The root broker accepts a trusted UID over a private Unix socket and a
one-time operator-issued approval. It never accepts arbitrary commands.
"""
import json
import stat
import os
import socket
import sqlite3
import struct
import time

from .systemd_jobs import JOBS, run_systemd_job


def verify_private_ledger(path):
    if not os.path.isabs(path):
        raise PermissionError("Absolute ledger path required")
    parent = os.lstat(os.path.dirname(path))
    info = os.lstat(path)
    if (parent.st_uid != 0 or parent.st_mode & 0o022 or
        not stat.S_ISDIR(parent.st_mode) or info.st_uid != 0 or
        not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
        info.st_nlink != 1):
        raise PermissionError("Unsafe broker ledger")

def provision_approval(path, approval_id, job):
    """Root-only manual provisioning; no socket issuance endpoint."""
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    verify_private_ledger(path)
    if type(job) is not str or job not in JOBS:
        raise PermissionError("Job not allowlisted")
    if (type(approval_id) is not str or len(approval_id) < 32 or
        len(approval_id) > 128 or not approval_id.isascii() or
        not approval_id.isalnum()):
        raise PermissionError("Invalid approval identifier")
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO approvals(id,job) VALUES (?,?)", (approval_id, job))


def initialize_ledger(db_path):
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    if not os.path.isabs(db_path) or os.path.lexists(db_path):
        raise PermissionError("New absolute ledger path required")
    parent = os.lstat(os.path.dirname(db_path))
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_mode & 0o022:
        raise PermissionError("Unsafe ledger directory")
    fd = os.open(db_path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    db = sqlite3.connect(db_path)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, job TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)")
        db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, approval_id TEXT, job TEXT, status TEXT, timestamp INTEGER)")
        db.commit()
    finally:
        db.close()


def execute_approved(db_path, approval_id, job, executor=run_systemd_job):
    if type(job) is not str or job not in JOBS:
        raise PermissionError("Job not allowlisted")
    if type(approval_id) is not str or len(approval_id) < 16 or len(approval_id) > 128 or not approval_id.isascii() or not approval_id.isalnum():
        raise PermissionError("Invalid approval")
    verify_private_ledger(db_path)
    db = sqlite3.connect(db_path, timeout=5, isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        cursor = db.execute("UPDATE approvals SET consumed=1 WHERE id=? AND job=? AND consumed=0", (approval_id, job))
        if cursor.rowcount != 1:
            db.rollback()
            raise PermissionError("Approval absent or consumed")
        db.execute("INSERT INTO audit(approval_id,job,status,timestamp) VALUES (?,?,?,?)", (approval_id, job, "started", int(time.time())))
        db.commit()
        try:
            result = executor(job)
        except Exception:
            db.execute("INSERT INTO audit(approval_id,job,status,timestamp) VALUES (?,?,?,?)", (approval_id, job, "failed", int(time.time())))
            raise
        db.execute("INSERT INTO audit(approval_id,job,status,timestamp) VALUES (?,?,?,?)", (approval_id, job, "completed", int(time.time())))
        return result
    finally:
        db.close()


def handle_connection(conn, trusted_uid, db_path):
    credentials = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    peer_uid = struct.unpack("3i", credentials)[1]
    if peer_uid != trusted_uid:
        raise PermissionError("Untrusted broker peer")
    conn.settimeout(5)
    data = bytearray()
    while len(data) <= 2048 and b"\n" not in data:
        chunk = conn.recv(512)
        if not chunk:
            break
        data.extend(chunk)
    if len(data) > 2048 or not data.endswith(b"\n") or data.count(b"\n") != 1:
        raise PermissionError("Invalid broker framing")
    try:
        request = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise PermissionError("Invalid broker JSON") from exc
    if not isinstance(request, dict) or set(request) != {"job", "approval_id"}:
        raise PermissionError("Invalid broker schema")
    result = execute_approved(db_path, request["approval_id"], request["job"])
    conn.sendall((json.dumps(result) + "\n").encode())
    return result


def serve_once(path, trusted_uid, db_path):
    if os.geteuid() != 0:
        raise PermissionError("Root broker required")
    if type(trusted_uid) is not int or trusted_uid <= 0:
        raise ValueError("Invalid trusted UID")
    verify_private_ledger(db_path)
    if not os.path.isabs(path) or os.path.lexists(path):
        raise PermissionError("Unsafe broker socket path")
    parent = os.lstat(os.path.dirname(path))
    if parent.st_uid != 0 or parent.st_mode & 0o022 or not stat.S_ISDIR(parent.st_mode):
        raise PermissionError("Unsafe broker socket path")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)
    try:
        listener.bind(path)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)
    listener.listen(1)
    listener.settimeout(10)
    try:
        conn, _ = listener.accept()
        with conn:
            return handle_connection(conn, trusted_uid, db_path)
    finally:
        listener.close()
        os.unlink(path)


def execute_signed_grant(db_path, envelope, verification_key,
                         executor=run_systemd_job, now=None, trusted_db_path=None):
    """Consume once and fence trusted lease writes through job completion.

    BEGIN IMMEDIATE on trusted SQLite prevents concurrent lease revocation
    through SQLite while a fixed job runs, including when WAL is enabled.
    """
    from .broker_grants import verify_broker_grant, verify_live_lease
    claims = verify_broker_grant(envelope, verification_key, now=now)
    verify_private_ledger(db_path)
    trusted = None
    if trusted_db_path is not None:
        if not os.path.isabs(trusted_db_path) or not os.path.isfile(trusted_db_path):
            raise PermissionError("Trusted database unavailable")
        trusted = sqlite3.connect("file:" + trusted_db_path + "?mode=rw",
                                  uri=True, timeout=5, isolation_level=None)
    db = None
    try:
        if trusted is not None:
            trusted.execute("BEGIN IMMEDIATE")
            verify_live_lease(trusted_db_path, claims, now=now, connection=trusted)
        db = sqlite3.connect(db_path, timeout=5, isolation_level=None)
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS signed_grant_consumptions(
            grant_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
            worker TEXT NOT NULL, lease_generation INTEGER NOT NULL,
            job TEXT NOT NULL, approval_id TEXT NOT NULL, status TEXT NOT NULL)""")
        try:
            db.execute("INSERT INTO signed_grant_consumptions VALUES (?,?,?,?,?,?,?)",
                       (claims["id"], claims["task"], claims["worker"],
                        claims["lease_generation"], claims["job"],
                        claims["approval"], "started"))
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise PermissionError("Grant replay denied") from exc
        db.commit()
        try:
            result = executor(claims["job"])
        except BaseException:
            db.execute("UPDATE signed_grant_consumptions SET status='failed' WHERE grant_id=?", (claims["id"],))
            raise
        db.execute("UPDATE signed_grant_consumptions SET status='completed' WHERE grant_id=?", (claims["id"],))
        return result
    finally:
        if trusted is not None:
            trusted.rollback()
            trusted.close()
        if db is not None:
            db.close()


def handle_signed_connection(conn, trusted_uid, ledger_path, trusted_db_path,
                             verification_key, executor=run_systemd_job, now=None):
    """Separate opt-in signed-grant socket protocol; no legacy fallback."""
    credentials = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    if struct.unpack("3i", credentials)[1] != trusted_uid:
        raise PermissionError("Untrusted signed broker peer")
    conn.settimeout(5)
    data = bytearray()
    while len(data) <= 4096 and b"\n" not in data:
        chunk = conn.recv(512)
        if not chunk:
            break
        data.extend(chunk)
    if len(data) > 4096 or not data.endswith(b"\n") or data.count(b"\n") != 1:
        raise PermissionError("Invalid signed broker framing")
    try:
        request = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise PermissionError("Invalid signed broker JSON") from exc
    if not isinstance(request, dict) or set(request) != {"grant"}:
        raise PermissionError("Invalid signed broker schema")
    from .broker_grants import verify_live_lease, verify_broker_grant
    claims = verify_broker_grant(request["grant"], verification_key, now=now)
    verify_live_lease(trusted_db_path, claims, now=now)
    result = execute_signed_grant(ledger_path, request["grant"], verification_key,
                                  executor=executor, now=now,
                                  trusted_db_path=trusted_db_path)
    conn.sendall((json.dumps(result) + "\n").encode())
    return result
