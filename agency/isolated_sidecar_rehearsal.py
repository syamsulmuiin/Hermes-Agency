"""Disposable real sidecar IPC acceptance against an already isolated broker.

Called only by the isolated candidate harness. Never uses production paths.
"""
import hashlib
import json
import os
import pwd
import secrets
import signal
import socket
import stat
import time

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


def run_sidecar_rehearsal(folder, db, broker_key, broker_socket, identity, repo):
    """Run actual operator_service child and IPC, then stop only that child."""
    if os.geteuid() != 0 or not folder.startswith("/run/hermes-staging/"):
        raise PermissionError("Isolated root staging only")
    from .operator_auth import LocalOperatorGate
    from .operator_service import main as sidecar_main
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
    pid = os.fork()
    if pid == 0:
        try:
            os.setgroups([])
            os.setgid(identity.pw_gid)
            os.setuid(identity.pw_uid)
            os.chdir(repo)
            sidecar_main(args)
        except BaseException:
            pass
        os._exit(1)
    try:
        deadline = time.monotonic() + 12
        while not os.path.exists(operator_socket) and time.monotonic() < deadline:
            ended, _ = os.waitpid(pid, os.WNOHANG)
            if ended:
                raise AssertionError("Isolated sidecar exited before socket ready")
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
    finally:
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            ended, _ = os.waitpid(pid, os.WNOHANG)
            if ended:
                break
            time.sleep(.05)
        else:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        if os.path.lexists(operator_socket):
            raise AssertionError("Sidecar did not clean up operator socket")
