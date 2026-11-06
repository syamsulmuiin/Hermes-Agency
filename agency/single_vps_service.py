"""Single-VPS, tool-free trusted service runner.

Run under a dedicated non-root service account, with a pre-provisioned private
state directory and a separate transport directory. Credentials must be issued
through trusted operator infrastructure, never from this socket or CLI.
"""
import argparse
import os

from .deployment_preflight import verify_deployment
from .security import SecureAgencyStore
from .orchestrator import WorkflowCoordinator
from .portable_runtime import PortableAgentRuntime
from .trusted import TrustedApprovalService
from .trusted_execution import TrustedAgentExecution
from .protected_service import serve_protected_once


def run_service(socket_path, state_dir, database, key_dir, client_gid,
                allowed_uids, secret):
    """Handle one authenticated request; supervisor may restart for next."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("Private signing key required")
    transport = os.path.dirname(os.path.abspath(socket_path))
    verify_deployment(transport, state_dir, database, key_dir,
                      client_gid, allowed_uids)
    store = SecureAgencyStore(database)
    try:
        runtime = PortableAgentRuntime(WorkflowCoordinator(store))
        approval = TrustedApprovalService(store, secret)
        boundary = TrustedAgentExecution(runtime, approval)
        return serve_protected_once(
            socket_path, boundary, allowed_uids, client_gid,
            (state_dir, database, key_dir)
        )
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Single-VPS trusted one-shot worker")
    parser.add_argument("--forever", action="store_true", help="Serve requests continuously")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--key-dir", required=True)
    parser.add_argument("--client-gid", type=int, required=True)
    parser.add_argument("--allow-uid", type=int, action="append", required=True)
    parser.add_argument("--secret-file", required=True)
    args = parser.parse_args(argv)
    if os.geteuid() == 0:
        parser.error("Trusted service must not run as root")
    # Read a pre-provisioned 0600 regular file only, never environment secrets.
    import stat
    fd = os.open(args.secret_file, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
            raise PermissionError("Secret file must be service-owned 0600")
        secret = os.read(fd, 65)
        if len(secret) != 64:
            raise ValueError("Signing secret must be 64 raw bytes")
    finally:
        os.close(fd)
    if args.forever:
        from .service_lifecycle import serve_forever
        return serve_forever(args.socket, args.state_dir, args.database,
                             args.key_dir, args.client_gid,
                             frozenset(args.allow_uid), secret)
    return run_service(args.socket, args.state_dir, args.database, args.key_dir,
                       args.client_gid, frozenset(args.allow_uid), secret)


if __name__ == "__main__":
    main()
