"""Deployment policy checks for a separate-UID trusted Unix service.

A group-traversable socket directory (0710) and group-writable socket (0660)
permit a dedicated client group to connect, while files in a different 0700
server-owned directory remain inaccessible. This module never changes modes,
owners, groups, or privileges.
"""
import os
import stat


def verify_cross_uid_transport(directory, socket_path, server_uid, client_gid):
    """Validate a pre-provisioned transport without modifying host permissions."""
    if type(server_uid) is not int or server_uid < 0 or type(client_gid) is not int or client_gid < 0:
        raise ValueError("Explicit server UID and client GID required")
    if not isinstance(directory, str) or not isinstance(socket_path, str):
        raise ValueError("Invalid paths")
    parent = os.path.abspath(directory)
    if os.path.dirname(os.path.abspath(socket_path)) != parent:
        raise PermissionError("Socket must be directly inside transport directory")
    folder = os.lstat(parent)
    if (not stat.S_ISDIR(folder.st_mode) or folder.st_uid != server_uid
        or folder.st_gid != client_gid or stat.S_IMODE(folder.st_mode) != 0o710):
        raise PermissionError("Transport directory ownership or mode invalid")
    entry = os.lstat(socket_path)
    if (not stat.S_ISSOCK(entry.st_mode) or entry.st_uid != server_uid
        or entry.st_gid != client_gid or stat.S_IMODE(entry.st_mode) != 0o660):
        raise PermissionError("Transport socket ownership or mode invalid")
    return True
