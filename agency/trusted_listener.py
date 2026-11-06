"""One-shot supervised Unix socket listener for trusted workflow submissions.

This is a testable building block, not a production daemon. The trusted
supervisor owns lifecycle, socket directory and process credentials. No shell,
network listener, credential issuance or agent tools are exposed.
"""
import os
import socket
import stat

from .trusted_local_service import verify_private_socket_directory
from .trusted_peer import serve_authenticated_peer


def listen_once(path, boundary, allowed_uids):
    """Accept at most one connection, with fail-closed peer checks.

    Requires an unused socket pathname inside a pre-existing private directory.
    Never removes an existing pathname. A 0700 directory intentionally restricts
    clients to the owning UID; cross-UID access needs a separate reviewed design.
    """
    if not isinstance(path, str) or not path or len(os.fsencode(path)) > 100:
        raise ValueError("Invalid Unix socket path")
    parent = os.path.dirname(os.path.abspath(path))
    verify_private_socket_directory(parent)
    if os.path.lexists(path):
        raise FileExistsError("Refusing to replace existing socket path")
    if (not isinstance(allowed_uids, frozenset) or not allowed_uids
        or any(type(uid) is not int or uid < 0 for uid in allowed_uids)):
        raise ValueError("Explicit UID allowlist required")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    bound = False
    try:
        listener.settimeout(3)
        listener.bind(path)
        bound = True
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        listener.listen(1)
        connection, _ = listener.accept()
        with connection:
            return serve_authenticated_peer(connection, boundary, allowed_uids)
    finally:
        listener.close()
        if bound:
            # Cleanup only the socket inode we created, not a replacement path.
            # If the pathname has been replaced, leave it for the supervisor.
            try:
                info = os.lstat(path)
                if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.geteuid():
                    os.unlink(path)
            except FileNotFoundError:
                pass
