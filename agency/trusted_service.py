"""Bounded sequential Unix socket service for trusted stage requests.

Not a daemon or privilege boundary by itself. The trusted supervisor must
provide a protected working directory, signing keys and database permissions.
"""
import os
import socket
import stat

from .trusted_local_service import verify_private_socket_directory
from .trusted_peer import serve_authenticated_peer
from .trusted_ack import serve_with_ack


def serve_bounded(path, boundary, allowed_uids, max_connections=1, acknowledged=False):
    """Accept a finite number of requests; reject failures without leaking details.

    An idle accept timeout terminates the service. This intentionally does not
    expose a public endpoint or implement background process management.
    """
    if type(acknowledged) is not bool:
        raise ValueError("Invalid acknowledgement mode")
    if type(max_connections) is not int or not 1 <= max_connections <= 100:
        raise ValueError("Invalid connection limit")
    if not isinstance(path, str) or not path or len(os.fsencode(path)) > 100:
        raise ValueError("Invalid socket path")
    if (not isinstance(allowed_uids, frozenset) or not allowed_uids
        or any(type(uid) is not int or uid < 0 for uid in allowed_uids)):
        raise ValueError("Explicit UID allowlist required")
    verify_private_socket_directory(os.path.dirname(os.path.abspath(path)))
    if os.path.lexists(path):
        raise FileExistsError("Socket path already exists")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    inode = None
    accepted = 0
    denied = 0
    try:
        listener.settimeout(3)
        listener.bind(path)
        inode = os.lstat(path).st_ino
        os.chmod(path, 0o600)
        listener.listen(4)
        for _ in range(max_connections):
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                break
            with connection:
                try:
                    if acknowledged:
                        if serve_with_ack(connection, boundary, allowed_uids) == "accepted":
                            accepted += 1
                        else:
                            denied += 1
                    else:
                        serve_authenticated_peer(connection, boundary, allowed_uids)
                        accepted += 1
                except (PermissionError, ValueError, TimeoutError, OSError):
                    denied += 1
        return {"accepted": accepted, "denied": denied}
    finally:
        listener.close()
        if inode is not None:
            try:
                info = os.lstat(path)
                if (stat.S_ISSOCK(info.st_mode) and info.st_uid == os.geteuid()
                    and info.st_ino == inode):
                    os.unlink(path)
            except FileNotFoundError:
                pass
