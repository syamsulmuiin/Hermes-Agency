"""Linux Unix-domain peer identity gate for trusted stage transport.

Peer UID is a second check, not a substitute for worker credentials.
A future daemon must call this gate before parsing any stage request.
"""
import socket
import struct
import sys

from .trusted_local_service import serve_one


def peer_credentials(connection):
    """Read kernel-supplied pid, uid, gid from an AF_UNIX connection."""
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("Peer credential verification unavailable")
    if not isinstance(connection, socket.socket) or connection.family != socket.AF_UNIX:
        raise PermissionError("Unix socket required")
    size = struct.calcsize("3i")
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
    if len(raw) != size:
        raise PermissionError("Incomplete peer credentials")
    pid, uid, gid = struct.unpack("3i", raw)
    if pid <= 0 or uid < 0 or gid < 0:
        raise PermissionError("Invalid peer identity")
    return {"pid": pid, "uid": uid, "gid": gid}


def serve_authenticated_peer(connection, boundary, allowed_uids):
    """Require an explicitly allowed peer UID before invoking the stage handler."""
    if (not isinstance(allowed_uids, frozenset) or not allowed_uids
        or any(type(uid) is not int or uid < 0 for uid in allowed_uids)):
        raise ValueError("Explicit nonempty UID allowlist required")
    peer = peer_credentials(connection)
    if peer["uid"] not in allowed_uids:
        raise PermissionError("Peer UID denied")
    return serve_one(connection, boundary)
