"""Mandatory preflight for a trusted cross-UID service.

The supervisor must provision the process identity and directories first.
This entrypoint does not create credentials, users, sockets or services and
never exposes a tool execution API.
"""
import os

from .cross_uid_listener import serve_cross_uid_once
from .private_state import verify_private_state


def serve_protected_once(path, boundary, allowed_uids, client_gid, trusted_state):
    """Serve one acknowledged request only after mandatory isolation checks."""
    uid = os.geteuid()
    if uid == 0:
        raise PermissionError("Trusted service must not run as root")
    if (not isinstance(allowed_uids, frozenset) or not allowed_uids
        or any(type(value) is not int or value < 0 or value == uid
               for value in allowed_uids)):
        raise PermissionError("Distinct client UID allowlist required")
    if (not isinstance(trusted_state, tuple) or len(trusted_state) != 3
        or any(not isinstance(item, (str, os.PathLike))
               for item in trusted_state)):
        raise ValueError("Mandatory trusted state configuration required")
    verify_private_state(*trusted_state)
    return serve_cross_uid_once(
        path, boundary, allowed_uids, client_gid,
        acknowledged=True, trusted_state=trusted_state
    )
