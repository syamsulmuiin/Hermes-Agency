"""Disposable real sidecar IPC acceptance against an already isolated broker.

Called only by the isolated candidate harness. Never uses production paths.
"""
import json
import os
import pwd
import secrets
import signal
import time
import traceback

from .isolated_operator_ipc import request_operator


def _write_new(path, data, uid, gid):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, data)
        os.fchown(fd, uid, gid)
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)


def _fixture(db, identity, operator_secret, credential_secret, job):
    """Provision pending approval under trusted UID; no root DB writes."""
    from .security import SecureAgencyStore
    from .trusted import TrustedApprovalService
    store = SecureAgencyStore(db)
    try:
        service = TrustedApprovalService(store, credential_secret)
        task = store.create_task("Isolated sidecar IPC rehearsal", "developer")
        approval = store.request_approval(task, "execute_shell", {"job": job}, "developer")
        lease = store.claim(task, "isolated-worker", ttl=180)
        worker = service.issue_credential("isolated-worker", "worker")
        return {"action": "approve_and_execute", "approval_id": approval,
                "task_id": task, "job": job, "worker_credential": worker,
                "lease_token": lease, "operator_secret_hex": operator_secret.hex()}
    finally:
        store.close()


def _trusted_fixture(db, identity, operator_secret, credential_secret, job):
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            os.setgroups([])
            os.setgid(identity.pw_gid)
            os.setuid(identity.pw_uid)
            os.umask(0o077)
            os.chmod(db, 0o600)
            for suffix in ("-wal", "-shm", "-journal"):
                if os.path.isfile(db + suffix):
                    os.chmod(db + suffix, 0o600)
            result = _fixture(db, identity, operator_secret, credential_secret, job)
            os.write(write_fd, json.dumps(result).encode())
            os._exit(0)
        except BaseException as exc:
            os.write(write_fd, ("ERROR:" + type(exc).__name__).encode())
            os._exit(1)
    os.close(write_fd)
    with os.fdopen(read_fd, "rb") as stream:
        raw = stream.read(16384)
    _, status = os.waitpid(pid, 0)
    if os.waitstatus_to_exitcode(status) != 0:
        raise AssertionError("Trusted fixture failed: " + raw.decode("ascii", "replace"))
    return json.loads(raw)


def run_sidecar_rehearsal(folder, db, broker_key, broker_socket, identity, repo, hold_callback=None):
    """Run actual operator_service child and IPC, then stop only that child."""
    if os.geteuid() != 0 or not folder.startswith("/run/hermes-staging/"):
        raise PermissionError("Isolated root staging only")
    from .operator_auth import LocalOperatorGate
    from .operator_service import main as sidecar_main
    # Import lazy boundary dependencies while still privileged. The forked
    # trusted UID cannot traverse the original checkout under /root.
    from .operator_service import _boundary_factory
    from .security import SecureAgencyStore
    from .orchestrator import WorkflowCoordinator
    from .portable_runtime import PortableAgentRuntime
    from .trusted import TrustedApprovalService
    from .trusted_execution import TrustedAgentExecution
    worker = next((p for p in (pwd.getpwnam("daemon"), pwd.getpwnam("root"))
                   if p.pw_uid not in (0, identity.pw_uid)), None)
    if worker is None:
        raise PermissionError("Distinct nonroot worker required")
    state = folder + "/trusted"
    key_dir = state + "/keys"
    os.mkdir(key_dir, 0o700)
    os.chown(key_dir, identity.pw_uid, identity.pw_gid)
    operator_dir = folder + "/operator"
    os.mkdir(operator_dir, 0o700)
    os.chown(operator_dir, identity.pw_uid, identity.pw_gid)
    operator_socket = operator_dir + "/operator.sock"
    credential_secret = secrets.token_bytes(64)
    operator_secret = secrets.token_bytes(32)
    salt, verifier = LocalOperatorGate.provision(operator_secret)
    secret_path = key_dir + "/credential.key"
    verifier_path = key_dir + "/operator-verifier.json"
    _write_new(secret_path, credential_secret, identity.pw_uid, identity.pw_gid)
    _write_new(verifier_path, json.dumps({
        "identity": "isolated-operator", "salt_hex": salt.hex(),
        "verifier_hex": verifier.hex()}).encode(), identity.pw_uid, identity.pw_gid)
    args = ["--state-dir", state, "--database", db, "--key-dir", key_dir,
            "--secret-file", secret_path, "--operator-socket", operator_socket,
            "--operator-verifier", verifier_path, "--broker-key", broker_key,
            "--broker-socket", broker_socket, "--worker-user", worker.pw_name]
    # Existing broker fixture may have created SQLite with process umask 022.
    # Normalize only disposable trusted files, using their owning UID.
    def prepare_private_database():
        child = os.fork()
        if child == 0:
            try:
                os.setgroups([])
                os.setgid(identity.pw_gid)
                os.setuid(identity.pw_uid)
                os.chmod(db, 0o600)
                for suffix in ("-wal", "-shm", "-journal"):
                    if os.path.isfile(db + suffix):
                        os.chmod(db + suffix, 0o600)
                os._exit(0)
            except BaseException:
                os._exit(1)
        _, status = os.waitpid(child, 0)
        if os.waitstatus_to_exitcode(status):
            raise AssertionError("Cannot secure isolated trusted database")

    prepare_private_database()
    error_read, error_write = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(error_read)
        try:
            os.setgroups([])
            os.setgid(identity.pw_gid)
            os.setuid(identity.pw_uid)
            os.chdir(repo)
            os.umask(0o077)
            sidecar_main(args)
        except BaseException as exc:
            # Print only exception type and traceback locations, never values,
            # secrets, arguments or raw exception messages.
            frames = traceback.extract_tb(exc.__traceback__)
            locations = ",".join(f.name + ":" + str(f.lineno) for f in frames[-6:])
            detail = type(exc).__name__ + " at " + locations
            print("ISOLATED_SIDECAR_CHILD_ERROR=" + detail, flush=True)
            os.write(error_write, type(exc).__name__.encode("ascii", "replace")[:100])
        os._exit(1)
    os.close(error_write)
    child_reaped = False
    try:
        deadline = time.monotonic() + 12
        while not os.path.exists(operator_socket) and time.monotonic() < deadline:
            ended, status = os.waitpid(pid, os.WNOHANG)
            if ended:
                child_reaped = True
                detail = os.read(error_read, 100).decode("ascii", "replace")
                raise AssertionError("Isolated sidecar exited before socket ready: " + (detail or "unknown"))
            time.sleep(.05)
        if not os.path.exists(operator_socket):
            raise AssertionError("Isolated sidecar socket timeout")
        print("SIDECAR_REAL_OPERATOR_SOCKET=PASS", flush=True)
        req = _trusted_fixture(db, identity, operator_secret, credential_secret, "noop")
        wrong = dict(req, operator_secret_hex="00" * 32)
        if request_operator(operator_socket, wrong) != "denied":
            raise AssertionError("Wrong operator secret accepted")
        print("SIDECAR_WRONG_SECRET_DENIED=PASS", flush=True)
        if request_operator(operator_socket, req) != "accepted":
            raise AssertionError("Real operator IPC grant rejected")
        print("SIDECAR_OPERATOR_TO_FENCED_BROKER=PASS", flush=True)
        if request_operator(operator_socket, req) != "denied":
            raise AssertionError("Operator replay accepted")
        print("SIDECAR_OPERATOR_REPLAY_DENIED=PASS", flush=True)
        if hold_callback is not None:
            hold_request = _trusted_fixture(db, identity, operator_secret,
                                            credential_secret, "identity")
            hold_callback(operator_socket, hold_request)
    finally:
        if not child_reaped:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    ended, _ = os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    break
                if ended:
                    break
                time.sleep(.05)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
        os.close(error_read)
        if os.path.lexists(operator_socket):
            raise AssertionError("Sidecar did not clean up operator socket")
