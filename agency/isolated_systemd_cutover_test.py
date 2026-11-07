"""Isolated real-systemd adapter for cutover orchestration acceptance.

Only fixed transient test units with a dedicated prefix are controlled.
No production broker, operator, socket, database or ledger is accessed.
"""
import contextlib
import hashlib
import hmac
import secrets
import sqlite3
import tempfile
import os
import subprocess
import time

from .production_cutover_controller import cutover, CutoverError
from .broker_grants import _canonical
from .security import fingerprint
from .systemd_broker import initialize_ledger, execute_signed_grant
from .fenced_unit_journal import recover_owned_units
from .fenced_startup_gate import require_recovered

PREFIX = "hermes-cutover-e2e-"
OLD = PREFIX + "legacy.service"
NEW = PREFIX + "fenced.service"


def _systemctl(*args):
    result = subprocess.run(["/usr/bin/systemctl", *args], capture_output=True,
                            text=True, timeout=15, check=False)
    return result.returncode, result.stdout.strip()


def _active(unit):
    code, output = _systemctl("is-active", unit)
    return code == 0 and output == "active"


def _stop(unit):
    subprocess.run(["/usr/bin/systemctl", "stop", unit], capture_output=True,
                   timeout=20, check=False)
    if _active(unit):
        raise RuntimeError("Unit did not stop: " + unit)


def _start(unit):
    if _active(unit):
        raise RuntimeError("Test unit already active: " + unit)
    command = ["/usr/bin/systemd-run", "--unit=" + unit.removesuffix(".service"),
               "--property=Type=simple", "--property=Restart=no",
               "--property=RuntimeMaxSec=90", "--collect",
               "/usr/bin/sleep", "75"]
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=15, check=False)
    if result.returncode:
        raise RuntimeError("Transient unit start failed")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _active(unit):
            return
        time.sleep(0.05)
    raise RuntimeError("Transient unit never became active")


class IsolatedSystemdAdapter:
    def __init__(self, failure=None, *, ledger=None, journal=None):
        self.failure = failure
        self.ledger = ledger
        self.journal = journal
        self.grant_id = secrets.token_hex(32)
        self.key = secrets.token_bytes(32)
        self.frozen = False
        self.route = "legacy"
        self.consumed = set()
        self.quarantined = False

    def _inject(self, phase):
        if self.failure == phase:
            self.failure = None
            raise RuntimeError("Injected failure: " + phase)

    @contextlib.contextmanager
    def admission_drain(self):
        # Isolated tests do not touch the production admission lock.
        self._inject("admission_drain")
        yield

    def attest(self):
        if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
            raise PermissionError("Root and real systemd required")
        if not _active(OLD) or _active(NEW):
            raise RuntimeError("Isolated legacy must be active and fenced inactive")
        self._inject("attest")

    def freeze(self):
        self.frozen = True
        self._inject("freeze")

    def quiesce(self):
        self._inject("quiesce")

    def stop_old(self):
        _stop(OLD)
        self._inject("stop_old")

    def bootstrap(self):
        require_recovered(self.journal)
        self._inject("bootstrap")

    def start_new(self):
        _start(NEW)
        self._inject("start_new")

    def route_new(self):
        self.route = "fenced"
        self._inject("route_new")

    def replay_probe(self):
        self._inject("replay_probe")
        now = time.time()
        claims = {"v": 1, "aud": "hermes-systemd-broker-v1",
                  "id": self.grant_id, "approval": "isolated-approval",
                  "task": "isolated-task", "worker": "isolated-worker",
                  "lease_generation": 1, "job": "noop",
                  "params_hash": fingerprint({"job": "noop"}),
                  "iat": now, "exp": now + 45}
        envelope = {"claims": claims, "signature":
                    hmac.new(self.key, _canonical(claims), hashlib.sha256).hexdigest()}
        result = execute_signed_grant(
            self.ledger, envelope, self.key, executor=lambda job: {"job": job})
        if result != {"job": "noop"}:
            raise AssertionError("Signed grant did not execute")
        self.consumed.add(self.grant_id)
        try:
            execute_signed_grant(
                self.ledger, envelope, self.key,
                executor=lambda job: (_ for _ in ()).throw(
                    AssertionError("Replay executed")))
        except PermissionError:
            pass
        else:
            raise AssertionError("Durable signed grant replay accepted")

    def health(self):
        self._inject("health")
        unit = OLD if self.route == "legacy" else NEW
        if not _active(unit):
            raise RuntimeError("Routed isolated systemd unit is not active")

    def rollback(self):
        self._inject("rollback")
        _stop(NEW)
        if not _active(OLD):
            _start(OLD)
        self.route = "legacy"
        require_recovered(self.journal)

    def unfreeze(self):
        self._inject("unfreeze")
        self.frozen = False

    def quarantine(self):
        # Only test-local state; not a production durable quarantine.
        self.quarantined = True
        self.frozen = True


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    for failure in (None, "start_new", "route_new", "health", "unfreeze"):
        _stop(OLD)
        _stop(NEW)
        with tempfile.TemporaryDirectory(prefix="hermes-cutover-ledger-") as fixture_dir:
            ledger = os.path.join(fixture_dir, "ledger.sqlite")
            journal = os.path.join(fixture_dir, "owned.sqlite")
            initialize_ledger(ledger)
            recover_owned_units(journal)
            adapter = IsolatedSystemdAdapter(
                failure=failure, ledger=ledger, journal=journal)
            _run_case(adapter, failure, ledger, journal)
    print("ISOLATED_SYSTEMD_CUTOVER_E2E=PASS", flush=True)
    print("REAL_SQLITE_REPLAY_LEDGER_TESTED=YES", flush=True)
    print("REAL_BROKER_PROTOCOL_TESTED=NO", flush=True)
    print("PRODUCTION_CUTOVER_AUTHORIZED=NO", flush=True)


def _run_case(adapter, failure, ledger, journal):
        try:
            _start(OLD)
            try:
                cutover(adapter)
                if failure is not None:
                    raise AssertionError("Injected failure unexpectedly succeeded")
                if not _active(NEW) or _active(OLD):
                    raise AssertionError("Success did not isolate fenced unit")
            except CutoverError:
                if failure is None:
                    raise
                if failure == "unfreeze":
                    if not _active(NEW) or _active(OLD) or adapter.route != "fenced":
                        raise AssertionError("Unfreeze failure lost successful handover")
                    if not adapter.quarantined or not adapter.frozen:
                        raise AssertionError("Unfreeze failure did not quarantine")
                else:
                    if not _active(OLD) or _active(NEW) or adapter.route != "legacy":
                        raise AssertionError("Rollback did not restore isolated legacy unit")
                    if adapter.frozen:
                        raise AssertionError("Admission remained frozen after verified rollback")
            with sqlite3.connect(ledger) as db:
                try:
                    rows = db.execute(
                        "SELECT grant_id,status FROM signed_grant_consumptions").fetchall()
                except sqlite3.OperationalError:
                    rows = []
            expected = [(adapter.grant_id, "completed")] if adapter.consumed else []
            if rows != expected:
                raise AssertionError("Replay ledger changed across handover/rollback")
            require_recovered(journal)
            print("ISOLATED_SYSTEMD_CUTOVER_" +
                  ("SUCCESS" if failure is None else failure.upper()) + "=PASS", flush=True)
        finally:
            _stop(NEW)
            _stop(OLD)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.parse_args(argv)
    run()


if __name__ == "__main__":
    main()
