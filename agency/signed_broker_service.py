"""Opt-in dedicated signed-grant broker transport and key controls.

This module never exposes legacy operator approvals over the signed socket.
"""
import json
import os
import socket
import stat

from .systemd_broker import handle_signed_connection, verify_private_ledger


def read_broker_key(path, trusted_uid, trusted_gid):
    if os.geteuid() != 0:
        raise PermissionError("Root broker required")
    if not os.path.isabs(path) or os.path.islink(path):
        raise PermissionError("Unsafe key path")
    parent = os.lstat(os.path.dirname(path))
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
            or parent.st_mode & 0o022):
        raise PermissionError("Unsafe key directory")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_gid != trusted_gid or stat.S_IMODE(info.st_mode) != 0o640
                or info.st_nlink != 1):
            raise PermissionError("Unsafe broker key permissions")
        key = os.read(fd, 65)
        if len(key) != 64:
            raise PermissionError("Broker key must be 64 raw bytes")
        return key
    finally:
        os.close(fd)


def provision_broker_key(path, trusted_gid):
    """Root-only exclusive creation; 0640 root:trusted-primary-GID."""
    if os.geteuid() != 0 or type(trusted_gid) is not int or trusted_gid <= 0:
        raise PermissionError("Root and dedicated trusted GID required")
    parent = os.lstat(os.path.dirname(path))
    if (not os.path.isabs(path) or parent.st_uid != 0
            or not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o022):
        raise PermissionError("Unsafe key directory")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, 0, trusted_gid)
        os.fchmod(fd, 0o640)
        os.write(fd, os.urandom(64))
        os.fsync(fd)
    finally:
        os.close(fd)


def serve_signed_once(socket_path, trusted_uid, trusted_gid, ledger_path,
                      trusted_db_path, key_path, executor=None, on_ready=None):
    """Root-only one-shot broker, socket 0660 root:trusted-primary-GID.

    The parent directory MUST be root-owned and traversable by trusted UID,
    but not accessible by the worker. No automatic production activation.
    """
    if os.geteuid() != 0 or min(trusted_uid, trusted_gid) <= 0:
        raise PermissionError("Root and dedicated trusted identity required")
    verify_private_ledger(ledger_path)
    key = read_broker_key(key_path, trusted_uid, trusted_gid)
    if not os.path.isabs(socket_path) or os.path.lexists(socket_path):
        raise PermissionError("Unsafe socket path")
    parent = os.lstat(os.path.dirname(socket_path))
    if (parent.st_uid != 0 or parent.st_gid != trusted_gid
            or not stat.S_ISDIR(parent.st_mode)
            or stat.S_IMODE(parent.st_mode) != 0o710):
        raise PermissionError("Broker socket directory must be root:trusted 0710")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        old = os.umask(0o177)
        try:
            listener.bind(socket_path)
        finally:
            os.umask(old)
        os.chown(socket_path, 0, trusted_gid)
        os.chmod(socket_path, 0o660)
        listener.listen(1)
        listener.settimeout(15)
        if on_ready is not None:
            on_ready()
        conn, _ = listener.accept()
        with conn:
            if executor is None:
                return handle_signed_connection(conn, trusted_uid, ledger_path,
                                                trusted_db_path, key)
            return handle_signed_connection(conn, trusted_uid, ledger_path,
                                            trusted_db_path, key, executor=executor)
    finally:
        listener.close()
        if os.path.lexists(socket_path):
            os.unlink(socket_path)


def submit_signed_grant(socket_path, envelope):
    """Trusted-side transport; not an authentication or issuance API."""
    payload = (json.dumps({"grant": envelope}, separators=(",", ":")) + "\n").encode()
    if len(payload) > 4096:
        raise ValueError("Grant too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(20)
        client.connect(socket_path)
        client.sendall(payload)
        reply = client.recv(4096)
    if not reply.endswith(b"\n"):
        raise PermissionError("Broker rejected request")
    return json.loads(reply)
