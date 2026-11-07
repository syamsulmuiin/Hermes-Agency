"""One-transaction staging cutover with a real candidate Unix socket and durable replay.

Only disposable /run/hermes-staging fixtures and prefixed transient test units.
Never changes production units, routes, credentials or databases.
"""
import argparse
import hashlib
import hmac
import json
import os
import pwd
import secrets
import sqlite3
import subprocess
import sys
import time

from .broker_grants import _canonical
from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import recover_owned_units
from .isolated_systemd_cutover_test import (
    IsolatedSystemdAdapter, OLD, NEW, _active, _start, _stop)
from .production_cutover_controller import cutover, CutoverError
from .real_candidate_socket_replay_e2e import BASE, CLIENT, wait_socket
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint
from .signed_broker_service import provision_broker_key
from .systemd_broker import initialize_ledger


class RealSocketCutoverAdapter(IsolatedSystemdAdapter):
    def __init__(self, *, ledger, journal, socket_path, database, key_path,
                 identity, grant, failure=None):
        super().__init__(failure=failure, ledger=ledger, journal=journal)
        self.socket_path = socket_path
        self.database = database
        self.key_path = key_path
        self.identity = identity
        self.grant = grant
        self.grant_id = grant["claims"]["id"]
        self.broker = None
        self.broker_log = None

    def _submit(self):
        request = json.dumps({"grant": self.grant}, separators=(",", ":"))
        result = subprocess.run(
            [sys.executable, "-c", CLIENT, self.socket_path, request],
            preexec_fn=lambda: (os.setgroups([]), os.setgid(self.identity.pw_gid),
                                 os.setuid(self.identity.pw_uid)),
            capture_output=True, text=True, timeout=25, check=False)
        if result.returncode:
            raise AssertionError("Trusted broker client failed: " + result.stderr)
        return result.stdout.strip()

    def start_new(self):
        if self.broker is not None:
            raise AssertionError("Candidate already started")
        self.broker_log = open(os.path.dirname(self.socket_path) + "/candidate.log", "ab", buffering=0)
        self.broker = subprocess.Popen(
            [sys.executable, "-m", "agency.fenced_broker_candidate",
             "--socket", self.socket_path, "--trusted-user", self.identity.pw_name,
             "--ledger", self.ledger, "--journal", self.journal,
             "--trusted-db", self.database, "--key", self.key_path,
             "--execute", "--isolated-test"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            stdin=subprocess.DEVNULL, stdout=self.broker_log,
            stderr=subprocess.STDOUT)
        wait_socket(self.socket_path, self.broker)
        self._inject("start_new")

    def replay_probe(self):
        self._inject("replay_probe")
        response = self._submit()
        if not response.startswith("{") or json.loads(response).get("exit_code") != 0:
            with open(os.path.dirname(self.socket_path) + "/candidate.log", "rb") as log:
                detail = log.read()[-3000:].decode("utf-8", "replace")
            raise AssertionError("Real candidate did not execute signed grant: " + response + "\\nCandidate diagnostic: " + detail)
        self.consumed.add(self.grant_id)
        if self._submit() != "DENIED_NO_REPLY":
            raise AssertionError("Real socket accepted replay")
        self._check_ledger()

    def _check_ledger(self):
        with sqlite3.connect(self.ledger) as db:
            rows = db.execute(
                "SELECT status FROM signed_grant_consumptions WHERE grant_id=?",
                (self.grant_id,)).fetchall()
        if rows != [("completed",)]:
            raise AssertionError("Durable grant ledger changed: " + repr(rows))

    def health(self):
        self._inject("health")
        if self.route == "legacy":
            if not _active(OLD):
                raise AssertionError("Legacy test unit unavailable")
        elif (self.broker is None or self.broker.poll() is not None
              or not os.path.exists(self.socket_path)):
            raise AssertionError("Real candidate socket unavailable")

    def stop_candidate(self):
        if self.broker is not None:
            if self.broker.poll() is None:
                self.broker.terminate()
                try:
                    self.broker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.broker.kill()
                    self.broker.wait(timeout=5)
            self.broker = None
        if os.path.lexists(self.socket_path):
            os.unlink(self.socket_path)
        if self.broker_log is not None:
            self.broker_log.close()
            self.broker_log = None

    def rollback(self):
        self._inject("rollback")
        self.stop_candidate()
        if not _active(OLD):
            _start(OLD)
        self.route = "legacy"
        require_recovered(self.journal)

    def assert_persistent_replay_after_restart(self):
        self._check_ledger()
        self.stop_candidate()
        require_recovered(self.journal)
        self.start_new()
        if self._submit() != "DENIED_NO_REPLY":
            raise AssertionError("Real candidate accepted replay after restart")
        self._check_ledger()


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and systemd required")
    identity = pwd.getpwnam("nobody")
    if identity.pw_uid == 0 or identity.pw_gid == 0:
        raise PermissionError("Non-root trusted identity required")
    base = os.stat(BASE)
    if base.st_uid != 0 or base.st_mode & 0o022 or not base.st_mode & 0o001:
        raise PermissionError("Unsafe staging base")
    for failure in (None, "health"):
        folder = BASE + "/combined-cutover-" + secrets.token_hex(8)
        os.mkdir(folder, 0o710)
        os.chown(folder, 0, identity.pw_gid)
        sock, ledger, journal, database, key_path = (
            folder + "/" + n for n in
            ("broker.sock", "ledger.sqlite", "journal.sqlite",
             "trusted.sqlite", "broker.key"))
        initialize_ledger(ledger)
        recover_owned_units(journal)
        provision_broker_key(key_path, identity.pw_gid)
        with open(key_path, "rb") as stream:
            key = stream.read()
        now = time.time()
        claims = {"v": 1, "aud": "hermes-systemd-broker-v1",
                  "id": secrets.token_hex(32), "approval": "test-approval",
                  "task": "test-task", "worker": "test-worker",
                  "lease_generation": 1, "job": "noop",
                  "params_hash": fingerprint({"job": "noop"}),
                  "iat": now, "exp": now + 90}
        grant = {"claims": claims, "signature":
                 hmac.new(key, _canonical(claims), hashlib.sha256).hexdigest()}
        fixture(database, claims)
        os.chown(database, identity.pw_uid, identity.pw_gid)
        os.chmod(database, 0o600)
        adapter = RealSocketCutoverAdapter(
            ledger=ledger, journal=journal, socket_path=sock, database=database,
            key_path=key_path, identity=identity, grant=grant, failure=failure)
        _stop(OLD)
        _stop(NEW)
        try:
            _start(OLD)
            if failure is None:
                result = cutover(adapter)
                if result.status != "PASS" or _active(OLD):
                    raise AssertionError("Handover did not complete")
                adapter.assert_persistent_replay_after_restart()
                print("COMBINED_REAL_SOCKET_HANDOVER_RESTART_REPLAY=PASS", flush=True)
            else:
                try:
                    cutover(adapter)
                except CutoverError:
                    pass
                else:
                    raise AssertionError("Injected health failure was accepted")
                if not _active(OLD) or adapter.route != "legacy" or adapter.frozen:
                    raise AssertionError("Rollback did not restore isolated legacy")
                adapter._check_ledger()
                print("COMBINED_REAL_SOCKET_ROLLBACK_LEDGER=PASS", flush=True)
            require_recovered(journal)
        finally:
            adapter.stop_candidate()
            _stop(NEW)
            _stop(OLD)
    print("COMBINED_REAL_SOCKET_CUTOVER_E2E=PASS", flush=True)
    print("PRODUCTION_CUTOVER_GO=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.parse_args(argv)
    run()


if __name__ == "__main__":
    main()
