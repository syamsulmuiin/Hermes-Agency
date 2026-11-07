"""Standalone opt-in trusted-UID operator sidecar for the live SQLite state.

Runs with the trusted PRIVATE group, not the worker transport group. Neither
the existing worker-stage daemon nor its group/socket permissions are altered.
The operator peer must be root and must know the offline-provisioned secret.
"""
import argparse
import os
import pwd
import signal
import stat

from .private_state import verify_private_state
from .operator_control import load_operator_verifier, serve_operator_forever
from .trusted_broker_adapter import _trusted_key


def load_private_secret(path):
    if os.geteuid() == 0 or not os.path.isabs(path):
        raise PermissionError("Non-root trusted secret path required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise PermissionError("Unsafe trusted signing secret")
        secret = os.read(fd, 65)
    finally:
        os.close(fd)
    if len(secret) != 64:
        raise PermissionError("Invalid trusted signing secret")
    return secret


def verify_private_broker_group(broker_key_path, worker_user):
    """Worker must NEVER belong to the broker signing-key group."""
    if os.geteuid() == 0 or not isinstance(worker_user, str) or not worker_user:
        raise PermissionError("Trusted non-root sidecar and worker identity required")
    worker = pwd.getpwnam(worker_user)
    if worker.pw_uid == os.geteuid():
        raise PermissionError("Worker must have distinct UID")
    # _trusted_key checks O_NOFOLLOW, root ownership, exact 0640 and
    # root:effective-primary-group. Preserve that stricter existing policy.
    _trusted_key(broker_key_path)
    worker_groups = set(os.getgrouplist(worker.pw_name, worker.pw_gid))
    if os.getegid() in worker_groups:
        raise PermissionError("Worker can read broker signing key group")
    return True


def _boundary_factory(database, secret):
    from .security import SecureAgencyStore
    from .orchestrator import WorkflowCoordinator
    from .portable_runtime import PortableAgentRuntime
    from .trusted import TrustedApprovalService
    from .trusted_execution import TrustedAgentExecution

    store = SecureAgencyStore(database)
    try:
        runtime = PortableAgentRuntime(WorkflowCoordinator(store))
        approval = TrustedApprovalService(store, secret)
        return TrustedAgentExecution(runtime, approval), store.close
    except BaseException:
        store.close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Opt-in local operator sidecar")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--key-dir", required=True)
    parser.add_argument("--secret-file", required=True)
    parser.add_argument("--operator-socket", required=True)
    parser.add_argument("--operator-verifier", required=True)
    parser.add_argument("--broker-key", required=True)
    parser.add_argument("--broker-socket", required=True)
    parser.add_argument("--worker-user", required=True)
    args = parser.parse_args(argv)
    if os.geteuid() == 0:
        parser.error("The operator sidecar must run as the non-root trusted UID")
    paths = (args.state_dir, args.database, args.key_dir, args.secret_file,
             args.operator_socket, args.operator_verifier, args.broker_key,
             args.broker_socket)
    if any(not os.path.isabs(path) for path in paths):
        parser.error("All filesystem paths must be absolute")
    verify_private_state(args.state_dir, args.database, args.key_dir)
    verify_private_broker_group(args.broker_key, args.worker_user)
    secret = load_private_secret(args.secret_file)
    verifier = load_operator_verifier(args.operator_verifier)
    stopping = [False]
    signal.signal(signal.SIGTERM, lambda *_: stopping.__setitem__(0, True))
    signal.signal(signal.SIGINT, lambda *_: stopping.__setitem__(0, True))
    serve_operator_forever(
        args.operator_socket,
        lambda: _boundary_factory(args.database, secret),
        verifier, args.broker_key, args.broker_socket,
        lambda: stopping[0],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
