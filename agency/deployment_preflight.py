"""Read-only deployment preflight for a protected cross-UID trusted service.

No provisioning, daemon startup, credential issuance, or tool execution.
Run as the intended non-root trusted service account.
"""
import argparse
import os
import stat

from .private_state import verify_private_state


def verify_deployment(transport_directory, state_directory, database_path,
                      key_directory, client_gid, allowed_uids):
    """Validate ownership and permissions before a protected listener starts."""
    uid = os.geteuid()
    if uid == 0:
        raise PermissionError("Trusted service must not run as root")
    if type(client_gid) is not int or client_gid < 0:
        raise ValueError("Explicit client group required")
    if (not isinstance(allowed_uids, frozenset) or not allowed_uids
        or any(type(value) is not int or value < 0 or value == uid
               for value in allowed_uids)):
        raise PermissionError("Explicit distinct client UIDs required")
    verify_private_state(state_directory, database_path, key_directory)
    entry = os.lstat(transport_directory)
    if (not stat.S_ISDIR(entry.st_mode) or entry.st_uid != uid
        or entry.st_gid != client_gid
        or stat.S_IMODE(entry.st_mode) != 0o710):
        raise PermissionError("Transport directory ownership or mode invalid")
    if os.path.commonpath((os.path.abspath(transport_directory),
                           os.path.abspath(state_directory))) == os.path.abspath(state_directory):
        raise PermissionError("Transport must not reside inside private state")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only trusted service preflight")
    parser.add_argument("--transport-dir", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--key-dir", required=True)
    parser.add_argument("--client-gid", type=int, required=True)
    parser.add_argument("--allow-uid", type=int, action="append", required=True)
    args = parser.parse_args(argv)
    try:
        verify_deployment(
            args.transport_dir, args.state_dir, args.database, args.key_dir,
            args.client_gid, frozenset(args.allow_uid)
        )
    except (OSError, ValueError, PermissionError) as exc:
        parser.exit(1, "Deployment preflight denied: " + type(exc).__name__ + "\n")
    print("Deployment preflight passed (permissions only; no cross-UID test)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
