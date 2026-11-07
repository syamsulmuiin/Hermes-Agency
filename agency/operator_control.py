"""Opt-in root-operator Unix control channel inside the trusted UID process.

Only an explicitly root-owned local operator process can connect. The worker
protocol and broker socket are separate; no credentials or signing keys are
issued to operator clients. This module does not deploy or enable a socket.
"""
import contextlib
import fcntl
import json
import os
import socket
import stat

from .trusted_peer import peer_credentials

MAX_OPERATOR_REQUEST = 12288


def parse_operator_request(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_OPERATOR_REQUEST:
        raise PermissionError("Invalid operator request size")
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise PermissionError("Invalid operator request") from exc
    if not isinstance(request, dict):
        raise PermissionError("Invalid operator request")
    operation = request.get("action")
    basic = {"action", "approval_id", "operator_secret_hex"}
    extended = basic | {"task_id", "job", "worker_credential", "lease_token"}
    if (operation == "approve" and set(request) == basic):
        pass
    elif (operation == "approve_and_execute" and set(request) == extended):
        pass
    else:
        raise PermissionError("Unsupported operator action")
    for field in set(request) - {"action"}:
        value = request[field]
        limit = 8192 if field == "worker_credential" else 256
        if type(value) is not str or not 1 <= len(value) <= limit:
            raise PermissionError("Invalid operator field")
    secret = request["operator_secret_hex"]
    if (len(secret) != 64 or any(char not in "0123456789abcdef" for char in secret)):
        raise PermissionError("Invalid operator secret encoding")
    if operation == "approve_and_execute":
        if (len(request["task_id"]) > 128 or len(request["approval_id"]) > 128
                or len(request["job"]) > 64 or len(request["lease_token"]) > 256):
            raise PermissionError("Invalid operator identity")
    elif len(request["approval_id"]) > 128:
        raise PermissionError("Invalid approval identity")
    return request


def load_operator_verifier(path):
    """Require a trusted-UID-owned 0600 regular verifier; never load plaintext."""
    if os.geteuid() == 0 or not os.path.isabs(path):
        raise PermissionError("Unsafe operator verifier path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            raise PermissionError("Unsafe operator verifier permissions")
        raw = os.read(fd, 1025)
        if len(raw) > 1024:
            raise PermissionError("Oversized operator verifier")
    finally:
        os.close(fd)
    try:
        record = json.loads(raw)
        if not isinstance(record, dict) or set(record) != {"identity", "salt_hex", "verifier_hex"}:
            raise ValueError("Invalid verifier record")
        identity = record["identity"]
        if type(identity) is not str or not identity or len(identity) > 128:
            raise ValueError("Invalid operator identity")
        salt = bytes.fromhex(record["salt_hex"])
        verifier = bytes.fromhex(record["verifier_hex"])
        if len(salt) < 16 or len(verifier) != 32:
            raise ValueError("Invalid operator verifier")
        return identity, salt, verifier
    except (ValueError, TypeError, KeyError) as exc:
        raise PermissionError("Invalid operator verifier") from exc


@contextlib.contextmanager
def operator_admission_lease(path="/run/hermes-operator/admission.lock"):
    """Shared nonblocking lock held across approval and broker execution.

    A maintenance controller must acquire an exclusive lock on this same
    inode and KEEP THE FILE DESCRIPTOR OPEN through the entire cutover.
    Existing sidecar processes must be restarted onto this code before
    the lock can provide a complete quiescence guarantee.
    """
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid not in (0, os.geteuid())
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise PermissionError("Unsafe admission lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PermissionError("Operator admission locked for maintenance") from exc
        try:
            # An unlink/recreate of the pathname must not split the lock
            # domain between an old inode and a replacement inode.
            current = os.stat(path, follow_symlinks=False)
            if (current.st_dev != info.st_dev or current.st_ino != info.st_ino
                    or current.st_nlink != 1):
                raise PermissionError("Admission lock inode changed")
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def dispatch_operator(boundary, request, verifier, broker_key_path, broker_socket_path):
    """Authenticate and decide; broker execution is only after actual approval."""
    with operator_admission_lease():
        operator_identity, salt, proof = verifier
        # Cooperative maintenance marker; not a security boundary or drain lock.
        # A race remains between this check and broker execution.
        freeze = "/run/hermes-operator/admission.freeze"
        if os.path.lexists(freeze):
            raise PermissionError("Operator admission frozen for maintenance")
        boundary.approve_operator_request(
            request["approval_id"], bytes.fromhex(request["operator_secret_hex"]),
            operator_identity, salt, proof,
        )
        if request["action"] == "approve_and_execute":
            return boundary.execute_operator_approved_job(
                request["approval_id"], request["task_id"], request["job"],
                request["worker_credential"], request["lease_token"],
                broker_key_path, broker_socket_path,
            )
        return None
    

def handle_operator_connection(connection, boundary, verifier,
                               broker_key_path, broker_socket_path):
    """Root SO_PEERCRED gate comes BEFORE reading any client-controlled bytes."""
    status = "denied"
    try:
        peer = peer_credentials(connection)
        if peer["uid"] != 0:
            raise PermissionError("Only explicitly root operator is authorized")
        connection.settimeout(3)
        raw = bytearray()
        while len(raw) <= MAX_OPERATOR_REQUEST:
            part = connection.recv(min(4096, MAX_OPERATOR_REQUEST + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
            if b"\n" in part:
                break
        if not raw.endswith(b"\n"):
            raise PermissionError("Missing request terminator")
        request = parse_operator_request(bytes(raw[:-1]))
        dispatch_operator(boundary, request, verifier, broker_key_path, broker_socket_path)
        status = "accepted"
    except (PermissionError, ValueError, TimeoutError, OSError, TypeError, KeyError):
        pass
    try:
        connection.sendall((json.dumps({"status": status}) + "\n").encode("ascii"))
    except OSError:
        pass
    return status


def serve_operator_forever(path, boundary_factory, verifier, broker_key_path,
                           broker_socket_path, stop):
    """Bind an owner-only socket in a separate pre-provisioned 0700 directory.

    Never touch the worker socket. The factory returns (boundary, close).
    """
    if os.geteuid() == 0 or not callable(boundary_factory) or not callable(stop):
        raise PermissionError("Trusted non-root operator listener required")
    if not os.path.isabs(path) or os.path.lexists(path):
        raise PermissionError("Operator socket must be a fresh absolute path")
    parent = os.lstat(os.path.dirname(path))
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700):
        raise PermissionError("Unsafe operator socket directory")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    inode = None
    try:
        # Parent is trusted-UID-owned 0700; avoid process-wide umask in a
        # multithreaded trusted service. Restrict socket to 0600 immediately.
        listener.bind(path)
        inode = os.lstat(path).st_ino
        os.chmod(path, 0o600)
        listener.listen(4)
        listener.settimeout(1)
        while not stop():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            with connection:
                boundary, close = boundary_factory()
                try:
                    handle_operator_connection(
                        connection, boundary, verifier, broker_key_path,
                        broker_socket_path,
                    )
                finally:
                    close()
    finally:
        listener.close()
        if inode is not None:
            try:
                current = os.lstat(path)
                if stat.S_ISSOCK(current.st_mode) and current.st_ino == inode and current.st_uid == os.geteuid():
                    os.unlink(path)
            except FileNotFoundError:
                pass
