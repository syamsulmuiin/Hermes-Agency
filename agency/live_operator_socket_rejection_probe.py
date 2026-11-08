"""Non-authorizing live operator socket rejection probe.

Sends only an invalid action. This is rejected by request parsing before
admission, approval, or broker execution; it cannot attest lock participation.
"""
import argparse
import json
import os
import pwd
import socket
import stat
import sys

from .production_runtime_evidence import capture, FREEZE

SOCKET = "/run/hermes-operator/operator.sock"


def probe(socket_path=SOCKET):
    before = capture()
    path = os.lstat(socket_path)
    if (not stat.S_ISSOCK(path.st_mode)
            or path.st_uid != pwd.getpwnam("hermes-trusted").pw_uid):
        raise PermissionError("Unexpected operator socket owner")
    if stat.S_IMODE(path.st_mode) != 0o600:
        raise PermissionError("Unexpected operator socket mode")
    if not FREEZE.exists():
        raise PermissionError("Freeze missing")
    # Unsupported action; no secret, approval ID, job, or execution fields.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(socket_path)
        client.sendall(b'{"action":"__attestation_invalid_action__"}\n')
        response = bytearray()
        while len(response) < 256:
            chunk = client.recv(256 - len(response))
            if not chunk:
                break
            response.extend(chunk)
            if b"\n" in response:
                break
    if bytes(response) != b'{"status": "denied"}\n' and bytes(response) != b'{"status":"denied"}\n':
        raise PermissionError("Unexpected operator response")
    after = capture()
    if (before["sidecar_pid"], before["lock_device"], before["lock_inode"]) != (
        after["sidecar_pid"], after["lock_device"], after["lock_inode"]):
        raise PermissionError("Runtime or lock identity changed")
    if not FREEZE.exists():
        raise PermissionError("Runtime state changed")
    return {"socket_rejection": "PASS", "runtime_identity": "PASS",
            "lock_inode_stability": "PASS",
            "live_admission_lock_participation": "NOT_ATTESTED",
            "approval_attempted": False, "broker_invoked_by_probe": False,
            "production_mutated_by_probe": False, "cutover_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only-rejection", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        result = probe()
    except (OSError, ValueError, PermissionError, TimeoutError) as exc:
        print("LIVE_SOCKET_REJECTION=NOT_ATTESTED")
        print("ERROR=" + type(exc).__name__)
        print("PRODUCTION_CUTOVER_GO=NO")
        return 2
    print(json.dumps(result, sort_keys=True))
    print("LIVE_SOCKET_REJECTION=PASS")
    print("PRODUCTION_CUTOVER_GO=NO")
    return 2


if __name__ == "__main__":
    sys.exit(main())
