"""Root-only IPC probe for a disposable trusted operator sidecar.

This is a rehearsal helper, not a production operator client. Never accepts
an arbitrary production socket: caller must supply a staging socket path.
"""
import json
import os
import socket
import stat


def request_operator(socket_path, payload):
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    if not isinstance(socket_path, str) or not socket_path.startswith("/run/hermes-staging/"):
        raise PermissionError("Only isolated staging operator sockets allowed")
    if not isinstance(payload, dict):
        raise TypeError("Operator request must be a dictionary")
    parent = os.path.dirname(socket_path)
    info = os.lstat(parent)
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid == 0:
        raise PermissionError("Operator socket directory must be trusted-owned 0700")
    entry = os.lstat(socket_path)
    if not stat.S_ISSOCK(entry.st_mode) or entry.st_uid != info.st_uid or stat.S_IMODE(entry.st_mode) != 0o600:
        raise PermissionError("Unsafe operator socket")
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(data) > 12288:
        raise ValueError("Operator request too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(socket_path)
        client.sendall(data)
        response = bytearray()
        while len(response) < 256:
            part = client.recv(256 - len(response))
            if not part:
                break
            response.extend(part)
            if b"\n" in part:
                break
    if not response.endswith(b"\n"):
        raise RuntimeError("Operator response incomplete")
    result = json.loads(response)
    if type(result) is not dict or result.get("status") not in ("accepted", "denied"):
        raise RuntimeError("Unexpected operator response")
    return result["status"]
