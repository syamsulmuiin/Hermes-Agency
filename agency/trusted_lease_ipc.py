"""Experimental trusted-UID lease-fence IPC; not production-wired.

The trusted process holds BEGIN IMMEDIATE until the root broker sends DONE or
disconnects. Broker peer UID and signed grant are checked before admission.
This module alone does not guarantee that a running systemd job is killed if
the trusted process crashes; production activation requires a job-lifetime
supervisor and corresponding crash tests.
"""
import json
import os
import socket
import struct

from .broker_grants import verify_broker_grant
from .trusted_lease_fence import fenced_lease

MAX_MESSAGE = 4096


def _read_line(conn, *, allow_clean_eof=False):
    data = bytearray()
    while len(data) <= MAX_MESSAGE:
        chunk = conn.recv(min(512, MAX_MESSAGE + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in data:
            break
    if not data and allow_clean_eof:\n        return None\n    if not data.endswith(b"\n") or data.count(b"\n") != 1 or len(data) > MAX_MESSAGE:
        raise PermissionError("Invalid lease IPC framing")
    return bytes(data[:-1])


def _send(conn, message):
    conn.sendall(json.dumps(message, separators=(",", ":")).encode() + b"\n")


def serve_fence_connection(conn, database, verification_key, *, root_uid=0, now=None,
                           cleanup_before_release=None):
    """Handle one connection; optional trusted cleanup occurs before lock release.

    cleanup_before_release is an operator-wired trusted callback, never a
    client-provided unit name. On cleanup failure the process must fail closed:
    a SQLite transaction lock alone cannot survive process termination.
    """
    if cleanup_before_release is not None and not callable(cleanup_before_release):
        raise TypeError("Trusted cleanup callback must be callable")
    peer = struct.unpack("3i", conn.getsockopt(
        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    if peer[1] != root_uid:
        raise PermissionError("Untrusted lease IPC peer")
    conn.settimeout(10)
    request = json.loads(_read_line(conn))
    if not isinstance(request, dict) or set(request) != {"grant"}:
        raise PermissionError("Invalid lease IPC request")
    claims = verify_broker_grant(request["grant"], verification_key, now=now)
    with fenced_lease(database, claims, now=now):
        _send(conn, {"status": "locked", "grant_id": claims["id"]})
        # Do not expire a valid fence merely because the job exceeds 10s.
        conn.settimeout(None)
        try:
            finish = json.loads(_read_line(conn))
            if finish != {"status": "done", "grant_id": claims["id"]}:
                raise PermissionError("Invalid lease IPC completion")
        finally:
            # Keep BEGIN IMMEDIATE held until the trusted-side job lifecycle
            # has been stopped and verified, including unexpected broker EOF.
            if cleanup_before_release is not None:
                cleanup_before_release(claims)
    _send(conn, {"status": "released", "grant_id": claims["id"]})
    return claims["id"]


def broker_fenced_job(conn, grant, executor):
    """Hold the IPC session across the fixed job; never accept a different ID."""
    claims = grant["claims"]
    conn.settimeout(10)
    _send(conn, {"grant": grant})
    response = json.loads(_read_line(conn))
    if response != {"status": "locked", "grant_id": claims["id"]}:
        raise PermissionError("Trusted lease not locked")
    # No job runs before the trusted process confirms a live locked lease.
    # The trusted endpoint must not time out while a permitted job runs.
    conn.settimeout(None)
    result = executor(claims["job"])
    _send(conn, {"status": "done", "grant_id": claims["id"]})
    response = json.loads(_read_line(conn))
    if response != {"status": "released", "grant_id": claims["id"]}:
        raise PermissionError("Trusted lease completion failed")
    return result
