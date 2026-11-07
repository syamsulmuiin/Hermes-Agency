"""Opt-in real fenced candidate socket + persistent replay acceptance.

Uses actual candidate entrypoint and trusted-UID client with private /run fixtures.
No production units, socket, journal, keys or databases are accessed.
"""
import argparse
import hashlib
import hmac
import json
import os
import pwd
import secrets
import socket
import sqlite3
import subprocess
import sys
import time

from .broker_grants import _canonical
from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import recover_owned_units, register_before_launch
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint
from .systemd_broker import initialize_ledger
from .signed_broker_service import provision_broker_key

BASE = "/run/hermes-staging"
CLIENT = """import json,socket,sys
s=socket.socket(socket.AF_UNIX)
s.settimeout(15)
s.connect(sys.argv[1])
s.sendall((sys.argv[2]+'\\n').encode())
try:
 data=s.recv(4096)
 print(data.decode().strip() if data else 'DENIED_NO_REPLY')
except (ConnectionResetError,TimeoutError,OSError):
 print('DENIED_NO_REPLY')
finally:
 s.close()
"""


def wait_socket(path, proc, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(path):
            return
        if proc.poll() is not None:
            raise RuntimeError("Candidate broker exited before socket ready")
        time.sleep(.05)
    raise RuntimeError("Candidate broker socket not ready")


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    identity = pwd.getpwnam("nobody")
    if identity.pw_uid == 0 or identity.pw_gid == 0:
        raise PermissionError("Dedicated non-root identity required")
    if not os.path.isdir(BASE):
        os.mkdir(BASE, 0o700)
    base_info = os.stat(BASE)
    if (base_info.st_uid != 0 or base_info.st_mode & 0o022
            or not base_info.st_mode & 0o001):
        raise PermissionError("Staging base must be root-owned, non-writable and traversable by trusted UID")
    folder = BASE + "/socket-e2e-" + secrets.token_hex(8)
    os.mkdir(folder, 0o710)
    os.chown(folder, 0, identity.pw_gid)
    socket_path = folder + "/broker.sock"
    ledger = folder + "/ledger.sqlite"
    journal = folder + "/journal.sqlite"
    database = folder + "/trusted.sqlite"
    key_path = folder + "/broker.key"
    broker = None
    try:
        initialize_ledger(ledger)
        recover_owned_units(journal)
        provision_broker_key(key_path, identity.pw_gid)
        key = open(key_path, "rb").read()
        now = time.time()
        claims = {"v": 1, "aud": "hermes-systemd-broker-v1",
                  "id": secrets.token_hex(32), "approval": "test-approval",
                  "task": "test-task", "worker": "test-worker",
                  "lease_generation": 1, "job": "noop",
                  "params_hash": fingerprint({"job": "noop"}),
                  "iat": now, "exp": now + 55}
        grant = {"claims": claims, "signature":
                 hmac.new(key, _canonical(claims), hashlib.sha256).hexdigest()}
        fixture(database, claims)
        os.chown(database, identity.pw_uid, identity.pw_gid)
        os.chmod(database, 0o600)
        request = json.dumps({"grant": grant}, separators=(",", ":"))

        def start():
            nonlocal broker
            broker = subprocess.Popen(
                [sys.executable, "-m", "agency.fenced_broker_candidate",
                 "--socket", socket_path, "--trusted-user", identity.pw_name,
                 "--ledger", ledger, "--journal", journal,
                 "--trusted-db", database, "--key", key_path,
                 "--execute", "--isolated-test"],
                cwd=os.path.dirname(os.path.dirname(__file__)),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True)
            wait_socket(socket_path, broker)

        def stop():
            nonlocal broker
            if broker is not None:
                if broker.poll() is None:
                    broker.kill()
                broker.wait(timeout=10)
                broker = None
            if os.path.lexists(socket_path):
                os.unlink(socket_path)

        def submit():
            result = subprocess.run(
                [sys.executable, "-c", CLIENT, socket_path, request],
                preexec_fn=lambda: (os.setgroups([]), os.setgid(identity.pw_gid),
                                     os.setuid(identity.pw_uid)),
                capture_output=True, text=True, timeout=20, check=False)
            if result.returncode:
                raise RuntimeError("Trusted client failed: " + result.stderr)
            return result.stdout.strip()

        start()
        response = submit()
        if not response.startswith("{") or json.loads(response).get("exit_code") != 0:
            raise AssertionError("Actual candidate socket did not execute signed noop: " + response)
        print("REAL_CANDIDATE_SOCKET_SIGNED_GRANT=PASS", flush=True)
        with sqlite3.connect(ledger) as db:
            row = db.execute("SELECT status FROM signed_grant_consumptions WHERE grant_id=?",
                             (claims["id"],)).fetchone()
        if row != ("completed",):
            raise AssertionError("Signed grant consumption not durable")
        print("REAL_CANDIDATE_LEDGER_COMMITTED=PASS", flush=True)
        stop()
        start()
        denied = submit()
        if denied != "DENIED_NO_REPLY":
            raise AssertionError("Replay was accepted after broker SIGKILL/restart: " + denied)
        with sqlite3.connect(ledger) as db:
            count = db.execute("SELECT count(*) FROM signed_grant_consumptions WHERE grant_id=?",
                               (claims["id"],)).fetchone()[0]
        if count != 1:
            raise AssertionError("Replay mutated persistent grant ledger")
        print("REAL_CANDIDATE_RESTART_REPLAY_DENIED=PASS", flush=True)
        stop()
        # Simulate crash uncertainty with a journal entry, then verify startup gate.
        unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
        register_before_launch(journal, unit)
        try:
            require_recovered(journal)
        except PermissionError:
            print("REAL_CANDIDATE_PENDING_JOURNAL_GATE=PASS", flush=True)
        else:
            raise AssertionError("Pending ownership journal was accepted")
        # Actual candidate must refuse to start while pending.
        broker = subprocess.Popen(
            [sys.executable, "-m", "agency.fenced_broker_candidate",
             "--socket", socket_path, "--trusted-user", identity.pw_name,
             "--ledger", ledger, "--journal", journal,
             "--trusted-db", database, "--key", key_path,
             "--execute", "--isolated-test"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        if broker.wait(timeout=8) == 0 or os.path.exists(socket_path):
            raise AssertionError("Actual candidate accepted pending ownership")
        broker = None
        recover_owned_units(journal)
        start()
        print("REAL_CANDIDATE_RECOVERED_RESTART=PASS", flush=True)
        print("REAL_CANDIDATE_SOCKET_REPLAY_E2E=PASS", flush=True)
        print("ACTIVE_JOB_SIGKILL_RECOVERY_E2E=NOT_TESTED", flush=True)
        print("PRODUCTION_CUTOVER_GO=NO", flush=True)
    finally:
        if broker is not None and broker.poll() is None:
            broker.kill()
            broker.wait(timeout=10)
        if os.path.lexists(socket_path):
            os.unlink(socket_path)
        # Preserve fixture on failure for investigation, never delete evidence.
        # Successful fixtures can be removed manually from /run/hermes-staging.


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.parse_args(argv)
    run()


if __name__ == "__main__":
    main()
