"""Explicit cross-UID Unix socket listener, without secret access for clients.

Deployment requires a pre-provisioned 0710 directory owned by the trusted UID
and dedicated client GID. Socket group must be provisioned by the supervisor
(e.g. service effective GID). This function never calls chown or chmod on the
directory, and never changes process credentials.
"""
import os
import socket
import stat

from .cross_uid_policy import verify_cross_uid_transport
from .trusted_peer import serve_authenticated_peer
from .trusted_ack import serve_with_ack


def serve_cross_uid_once(path, boundary, allowed_uids, client_gid, acknowledged=False):
    """Handle one authenticated request; fail closed on mismatched ownership."""
    if type(acknowledged) is not bool:
        raise ValueError("Invalid acknowledgement mode")
    if not isinstance(path, str) or not path or len(os.fsencode(path)) > 100:
        raise ValueError("Invalid socket path")
    if (not isinstance(allowed_uids, frozenset) or not allowed_uids
        or any(type(uid) is not int or uid < 0 for uid in allowed_uids)
        or os.geteuid() in allowed_uids):
        raise ValueError("Only explicitly approved distinct client UIDs are allowed")
    if type(client_gid) is not int or client_gid < 0:
        raise ValueError("Dedicated client GID required")
    parent = os.path.dirname(os.path.abspath(path))
    folder = os.lstat(parent)
    if (not stat.S_ISDIR(folder.st_mode) or folder.st_uid != os.geteuid()
        or folder.st_gid != client_gid or stat.S_IMODE(folder.st_mode) != 0o710):
        raise PermissionError("Transport directory not pre-provisioned")
    if os.path.lexists(path):
        raise FileExistsError("Refusing existing socket path")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    inode = None
    try:
        listener.settimeout(3)
        listener.bind(path)
        inode = os.lstat(path).st_ino
        os.chmod(path, 0o660)
        verify_cross_uid_transport(parent, path, os.geteuid(), client_gid)
        listener.listen(1)
        connection, _ = listener.accept()
        with connection:
            if acknowledged:
                return serve_with_ack(connection, boundary, allowed_uids)
            return serve_authenticated_peer(connection, boundary, allowed_uids)
    finally:
        listener.close()
        if inode is not None:
            try:
                entry = os.lstat(path)
                if (stat.S_ISSOCK(entry.st_mode) and entry.st_uid == os.geteuid()
                    and entry.st_ino == inode):
                    os.unlink(path)
            except FileNotFoundError:
                pass
