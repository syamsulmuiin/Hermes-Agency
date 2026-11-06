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
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)
    try:
        listener.bind(path)
    finally:
        os.umask(old)
    listener.listen(1)
    listener.settimeout(10)
    try:
        conn, _ = listener.accept()
        with conn:
            return handle_connection(conn, trusted_uid, db_path)
    finally:
        listener.close()
        os.unlink(path)
