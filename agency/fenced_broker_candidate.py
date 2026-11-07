"""Opt-in persistent fenced signed broker candidate; never auto-activated.

Each accepted signed grant uses the isolated trusted-UID lease peer, root
stop controller, replay ledger and durable ownership journal. Independent
systemd recovery and startup gating MUST be installed before any deployment.
"""
import argparse
import json
import os
import pwd
import signal
import socket
import stat
import struct

from .broker_grants import verify_broker_grant
from .fenced_staging_launcher import run_staging_session
from .fenced_startup_gate import require_recovered
from .signed_broker_service import read_broker_key
from .systemd_broker import verify_private_ledger

MAX_REQUEST = 4096


def _read_grant(conn, trusted_uid):
    peer = struct.unpack("3i", conn.getsockopt(
        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    if peer[1] != trusted_uid:
        raise PermissionError("Untrusted broker client")
    conn.settimeout(5)
    data = bytearray()
    while len(data) <= MAX_REQUEST and b"\n" not in data:
        chunk = conn.recv(512)
        if not chunk:
            break
        data.extend(chunk)
    if (len(data) > MAX_REQUEST or not data.endswith(b"\n")
            or data.count(b"\n") != 1):
        raise PermissionError("Invalid signed grant framing")
    try:
        request = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise PermissionError("Invalid signed grant JSON") from exc
    if not isinstance(request, dict) or set(request) != {"grant"}:
        raise PermissionError("Invalid signed grant schema")
    return request["grant"]


def serve_candidate(path, uid, gid, ledger, journal, trusted_db, key_path, *,
                    stop=None, session=run_staging_session):
    if os.geteuid() != 0 or uid <= 0 or gid <= 0:
        raise PermissionError("Root and dedicated trusted UID required")
    if pwd.getpwuid(uid).pw_gid != gid:
        raise PermissionError("Trusted primary group mismatch")
    verify_private_ledger(ledger)
    require_recovered(journal)
    read_broker_key(key_path, uid, gid)
    parent = os.lstat(os.path.dirname(path))
    if (not os.path.isabs(path) or os.path.lexists(path)
            or parent.st_uid != 0 or parent.st_gid != gid
            or not stat.S_ISDIR(parent.st_mode)
            or stat.S_IMODE(parent.st_mode) != 0o710):
        raise PermissionError("Unsafe signed broker socket")
    if stop is None:
        stop = lambda: False
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        old = os.umask(0o177)
        try:
            listener.bind(path)
        finally:
            os.umask(old)
        try:
            os.chown(path, 0, gid)
            os.chmod(path, 0o660)
            listener.listen(8)
            listener.settimeout(1)
            while not stop():
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    continue
                with conn:
                    try:
                        # Re-check journal after every request. No unfenced fallback.
                        require_recovered(journal)
                        key = read_broker_key(key_path, uid, gid)
                        grant = _read_grant(conn, uid)
                        verify_broker_grant(grant, key)
                        result = session(grant, key, journal, trusted_db,
                                         trusted_uid=uid, trusted_gid=gid,
                                         ledger=ledger)
                        conn.sendall((json.dumps(result) + "\n").encode())
                    except (PermissionError, ValueError, OSError) as exc:
                        print(json.dumps({"fenced_broker": "denied",
                                          "reason": type(exc).__name__}), flush=True)
                        # Journal uncertainty is a hard service failure.
                        require_recovered(journal)
            return True
        finally:
            if os.path.lexists(path):
                os.unlink(path)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--trusted-user", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--trusted-db", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    identity = pwd.getpwnam(args.trusted_user)
    stopping = [False]
    signal.signal(signal.SIGTERM, lambda *_: stopping.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *_: stopping.__setitem__(0, True))
    serve_candidate(args.socket, identity.pw_uid, identity.pw_gid,
                    args.ledger, args.journal, args.trusted_db, args.key,
                    stop=lambda: stopping[0])


if __name__ == "__main__":
    main()
