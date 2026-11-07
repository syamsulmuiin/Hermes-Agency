"""Opt-in real multiprocess trusted approval -> root broker -> systemd test.

Run ONLY as root on a disposable acceptance environment. Does not modify
the live Hermes trusted service or install a persistent broker.
"""
import json
import hashlib
import hmac
import os
import pwd
import socket
import sqlite3
import tempfile
import time
from pathlib import Path

from .broker_grants import issue_broker_grant
from .security import SecureAgencyStore
from .trusted import TrustedApprovalService
from .systemd_broker import initialize_ledger
from .signed_broker_service import (provision_broker_key, read_broker_key,
                                    serve_signed_once, submit_signed_grant)


def _child(uid, gid, callback):
    pid = os.fork()
    if pid == 0:
        try:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
            callback()
        except BaseException as exc:
            print("child failure:", type(exc).__name__, str(exc), flush=True)
            os._exit(1)
        os._exit(0)
    return pid


def _wait(pid):
    _, status = os.waitpid(pid, 0)
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
        raise RuntimeError("Isolated acceptance child failed")


def run_acceptance(trusted_user="hermes-trusted", worker_user="hermes-worker"):
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    trusted = pwd.getpwnam(trusted_user)
    worker = pwd.getpwnam(worker_user)
    if (trusted.pw_uid == worker.pw_uid or
            trusted.pw_gid in os.getgrouplist(worker_user, worker.pw_gid)):
        raise PermissionError("Trusted and worker identities must be distinct")
    with tempfile.TemporaryDirectory(prefix="hermes-full-e2e-") as base:
        os.chmod(base, 0o711)
        socket_dir = os.path.join(base, "broker")
        state_dir = os.path.join(base, "trusted")
        os.mkdir(socket_dir, 0o710)
        os.chown(socket_dir, 0, trusted.pw_gid)
        os.mkdir(state_dir, 0o700)
        os.chown(state_dir, trusted.pw_uid, trusted.pw_gid)
        socket_path = os.path.join(socket_dir, "broker.sock")
        key_path = os.path.join(base, "broker.key")
        ledger_path = os.path.join(base, "ledger.sqlite")
        trusted_db = os.path.join(state_dir, "trusted.sqlite")
        result_path = os.path.join(state_dir, "result.json")
        envelope_path = os.path.join(state_dir, "grant.json")
        provision_broker_key(key_path, trusted.pw_gid)
        initialize_ledger(ledger_path)

        def worker_denial():
            try:
                with socket.socket(socket.AF_UNIX) as sock:
                    sock.connect(socket_path)
            except PermissionError:
                return
            raise AssertionError("Worker connected to restricted broker socket")

        def trusted_client():
            store = SecureAgencyStore(trusted_db)
            try:
                auth = TrustedApprovalService(store, b"s"*64)
                task = store.create_task("Isolated broker acceptance", "developer")
                lease = store.claim(task, "worker", ttl=60)
                worker_cred = auth.issue_credential("worker", "worker")
                approval = store.request_approval(task, "execute_shell", {"job":"noop"}, "developer")
                reviewer = auth.issue_credential("operator", "approver")
                auth.decide(approval, reviewer, True)
                with open(key_path, "rb") as handle:
                    key = handle.read()
                envelope = issue_broker_grant(auth, approval, task, "noop",
                                              worker_cred, lease, key)
                Path(envelope_path).write_text(json.dumps(envelope))
                store.close()
                deadline = time.monotonic() + 10
                while not os.path.exists(socket_path) and time.monotonic() < deadline:
                    time.sleep(0.05)
                result = submit_signed_grant(socket_path, envelope)
                if result.get("isolated_backend") != "systemd" or result.get("exit_code") != 0:
                    raise AssertionError("Real systemd sandbox not confirmed")
                # The one-shot listener closes after the first execution.
                # Replay is verified separately against persistent ledger.
                Path(result_path).write_text(json.dumps(result))
            finally:
                store.close()

        child = _child(trusted.pw_uid, trusted.pw_gid, trusted_client)
        try:
            serve_signed_once(socket_path, trusted.pw_uid, trusted.pw_gid,
                              ledger_path, trusted_db, key_path,
                              on_ready=lambda: _wait(_child(
                                  worker.pw_uid, worker.pw_gid, worker_denial)))
        finally:
            _wait(child)
        with sqlite3.connect(ledger_path) as db:
            row = db.execute("SELECT status FROM signed_grant_consumptions").fetchone()
        if row != ("completed",):
            raise AssertionError("Broker audit incomplete")
        # Negative attempts use fresh root broker processes/sockets, preserving
        # the real consumed ledger. The same signed grant must never run twice.
        def negative_attempt(envelope, expected):
            def client():
                deadline = time.monotonic() + 10
                while not os.path.exists(socket_path) and time.monotonic() < deadline:
                    time.sleep(0.05)
                try:
                    submit_signed_grant(socket_path, envelope)
                except (OSError, PermissionError):
                    return
                raise AssertionError(expected + " unexpectedly executed")
            pid = _child(trusted.pw_uid, trusted.pw_gid, client)
            try:
                try:
                    serve_signed_once(socket_path, trusted.pw_uid, trusted.pw_gid,
                                      ledger_path, trusted_db, key_path)
                except PermissionError:
                    pass
                else:
                    raise AssertionError(expected + " broker accepted invalid grant")
            finally:
                _wait(pid)

        envelope = json.loads(Path(envelope_path).read_text())
        negative_attempt(envelope, "replay")
        expired = json.loads(json.dumps(envelope))
        expired["claims"]["exp"] = expired["claims"]["iat"] + 1
        with open(key_path, "rb") as handle:
            key = handle.read()
        raw = json.dumps(expired["claims"], sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
        expired["signature"] = hmac.new(key, raw, hashlib.sha256).hexdigest()
        delay = expired["claims"]["exp"] - time.time() + 0.2
        if delay > 0:
            time.sleep(delay)
        negative_attempt(expired, "expired signed grant")
        with sqlite3.connect(ledger_path) as db:
            count = db.execute("SELECT COUNT(*) FROM signed_grant_consumptions").fetchone()[0]
        if count != 1:
            raise AssertionError("Negative attempts consumed extra grants")
        return {"real_trusted_approval_to_systemd": "PASS",
                "worker_socket_denied": "PASS", "grant_consumed": "PASS",
                "replay_socket_denied": "PASS",
                "tampered_expiry_socket_denied": "PASS",
                "production_service_modified": False}


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), indent=2))
