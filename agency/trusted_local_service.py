"""Single-request Unix socket transport for the trusted workflow boundary.

This module does not start a daemon, issue credentials or run tools. A trusted
supervisor must bind the socket in a private directory and run the server under
a separate OS identity with exclusive database/key access.
"""
import json
import os
import socket
import stat

from .trusted_protocol import MAX_REQUEST_BYTES, parse_stage_request


def serve_one(connection, boundary):
    """Process exactly one bounded request on an already accepted connection."""
    connection.settimeout(3)
    chunks = bytearray()
    while len(chunks) <= MAX_REQUEST_BYTES:
        part = connection.recv(min(4096, MAX_REQUEST_BYTES + 1 - len(chunks)))
        if not part:
            break
        chunks.extend(part)
    if len(chunks) > MAX_REQUEST_BYTES:
        raise ValueError("Request too large")
    request = parse_stage_request(bytes(chunks))
    return boundary.submit_stage(
        request["task_id"], request["agent"], request["result"],
        request["worker_credential"],
    )


def verify_private_socket_directory(path):
    """Require a pre-existing owner-only directory, not a symlink."""
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError("Socket directory must be a private real directory")
    if info.st_uid != os.geteuid():
        raise PermissionError("Socket directory must be owned by service user")
    return True
