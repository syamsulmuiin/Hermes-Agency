"""Bounded acknowledgement protocol for trusted Unix socket stage requests.

Never return exception text, worker credentials, task content, or DB details.
The response is advisory; clients must not treat a missing response as success.
"""
import json
import socket

from .trusted_peer import serve_authenticated_peer

MAX_ACK_BYTES = 128
_ACKS = frozenset({"accepted", "denied"})


def serve_with_ack(connection, boundary, allowed_uids):
    """Process a single request and send only an opaque success/failure marker."""
    status = "denied"
    try:
        serve_authenticated_peer(connection, boundary, allowed_uids)
        status = "accepted"
    except (PermissionError, ValueError, TimeoutError, OSError):
        pass
    # No sensitive exception details are ever serialized.
    try:
        connection.sendall((json.dumps({"status": status}) + "\n").encode("ascii"))
    except OSError:
        pass
    return status


def read_ack(connection):
    """Require exactly one small, newline-terminated acknowledgement."""
    raw = bytearray()
    while len(raw) <= MAX_ACK_BYTES:
        part = connection.recv(min(32, MAX_ACK_BYTES + 1 - len(raw)))
        if not part:
            break
        raw.extend(part)
        if b"\n" in part:
            break
    if len(raw) > MAX_ACK_BYTES or not raw.endswith(b"\n"):
        raise PermissionError("Missing or malformed trusted acknowledgement")
    try:
        obj = json.loads(raw[:-1].decode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise PermissionError("Malformed trusted acknowledgement") from exc
    if not isinstance(obj, dict) or set(obj) != {"status"} or obj["status"] not in _ACKS:
        raise PermissionError("Invalid trusted acknowledgement")
    if obj["status"] != "accepted":
        raise PermissionError("Trusted service denied request")
    return True
