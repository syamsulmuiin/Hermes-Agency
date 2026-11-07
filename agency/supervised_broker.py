"""Opt-in supervised root broker; never grants worker access.

The broker only receives signed fixed-job grants from the trusted UID.
Install and enable the unit manually after production acceptance.
"""
import argparse
import json
import os
import pwd
import signal
import socket
import stat

from .signed_broker_service import read_broker_key
from .systemd_broker import handle_signed_connection, verify_private_ledger


def serve_forever(path, trusted_uid, trusted_gid, ledger, trusted_db, key_path,
                  stop=None, executor=None, require_fenced=False):
    if require_fenced:
        # No production-grade persistent fenced listener is wired yet.
        # Reject before binding the socket, never fall back to legacy execution.
        raise PermissionError("Fenced production broker not installed")
    if os.geteuid() != 0 or trusted_uid <= 0 or trusted_gid <= 0:
        raise PermissionError("Root broker required")
    if pwd.getpwuid(trusted_uid).pw_gid != trusted_gid:
        raise PermissionError("Trusted primary group mismatch")
    verify_private_ledger(ledger)
    read_broker_key(key_path, trusted_uid, trusted_gid)
    parent = os.lstat(os.path.dirname(path))
    if (not os.path.isabs(path) or os.path.lexists(path)
            or parent.st_uid != 0 or parent.st_gid != trusted_gid
            or not stat.S_ISDIR(parent.st_mode)
            or stat.S_IMODE(parent.st_mode) != 0o710):
        raise PermissionError("Unsafe broker socket")
    if stop is None:
        stop = lambda: False
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)
    try:
        listener.bind(path)
    finally:
        os.umask(old)
    try:
        os.chown(path, 0, trusted_gid)
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
                    # Reopen on each request so atomic key replacement takes effect.
                    key = read_broker_key(key_path, trusted_uid, trusted_gid)
                    if executor is None:
                        handle_signed_connection(conn, trusted_uid, ledger,
                                                 trusted_db, key)
                    else:
                        handle_signed_connection(conn, trusted_uid, ledger,
                                                 trusted_db, key, executor=executor)
                except (PermissionError, ValueError, OSError) as exc:
                    # No secrets, grant content or signatures in logs.
                    print(json.dumps({"broker":"denied",
                                      "reason":type(exc).__name__}), flush=True)
        return True
    finally:
        listener.close()
        if os.path.lexists(path):
            os.unlink(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--trusted-user", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--trusted-db", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--require-fenced", action="store_true")
    args = parser.parse_args()
    identity = pwd.getpwnam(args.trusted_user)
    stopping = [False]
    signal.signal(signal.SIGTERM, lambda *_: stopping.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *_: stopping.__setitem__(0, True))
    serve_forever(args.socket, identity.pw_uid, identity.pw_gid,
                  args.ledger, args.trusted_db, args.key,
                  stop=lambda: stopping[0], require_fenced=args.require_fenced)


if __name__ == "__main__":
    main()
