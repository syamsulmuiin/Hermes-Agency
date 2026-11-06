"""Conservative recovery of a stale Unix listener socket.

Never remove non-sockets, symlinks, sockets of another owner, or any socket
that accepts connections. Must be called only by the trusted service account
while its single-instance supervisor prevents competing service instances.
"""
import os
import socket
import stat


def recover_stale_socket(path):
    try:
        entry = os.lstat(path)
    except FileNotFoundError:
        return False
    if not stat.S_ISSOCK(entry.st_mode) or entry.st_uid != os.geteuid():
        raise PermissionError("Existing socket path is not owned trusted socket")
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(1)
    try:
        try:
            connection.connect(path)
        except ConnectionRefusedError:
            pass
        except OSError as exc:
            raise PermissionError("Socket liveness cannot be established") from exc
        else:
            raise PermissionError("Socket is accepting connections")
    finally:
        connection.close()
    # Reject replacement between the initial inspection and unlink.
    current = os.lstat(path)
    if (not stat.S_ISSOCK(current.st_mode) or current.st_ino != entry.st_ino
        or current.st_dev != entry.st_dev or current.st_uid != entry.st_uid):
        raise PermissionError("Socket changed during recovery")
    os.unlink(path)
    return True
