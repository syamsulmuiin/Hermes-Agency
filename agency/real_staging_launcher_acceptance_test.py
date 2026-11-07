"""Opt-in real launcher integration smoke test using synthetic grant and systemd.

This exercises the NEW staging launcher with a non-root trusted peer and
stop-before-release, not broker SIGKILL recovery. Run only with --execute.
"""
import argparse
import hashlib
import hmac
import os
import pwd
import secrets
import sqlite3
import tempfile
import time

from .broker_grants import _canonical
from .fenced_staging_broker import unit_for_grant
from .fenced_staging_launcher import run_staging_session
from .fenced_startup_gate import require_recovered
from .fenced_systemd_supervisor import stop_and_verify_unit
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint


def exercise():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Requires root and real systemd")
    identity = pwd.getpwnam("nobody")
    if identity.pw_uid == 0 or identity.pw_gid == 0:
        raise PermissionError("Dedicated nonroot test identity required")
    base = "/run/hermes-staging"
    os.makedirs(base, mode=0o700, exist_ok=True)
    info = os.lstat(base)
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise PermissionError("Unsafe staging root")
    # Non-root trusted peer must traverse this root-owned staging parent.
    # No directory listing or non-root writes are granted.
    os.chmod(base, 0o711)
    with tempfile.TemporaryDirectory(prefix="accept-", dir=base) as folder:
        os.chmod(folder, 0o711)
        journal = folder + "/owned.sqlite"
        # SQLite rollback journal requires directory write access.
        # The ownership journal remains in the root-owned parent.
        trusted_dir = folder + "/trusted"
        os.mkdir(trusted_dir, 0o700)
        os.chown(trusted_dir, identity.pw_uid, identity.pw_gid)
        database = trusted_dir + "/trusted.sqlite"
        key = secrets.token_bytes(32)
        now = time.time()
        claims = {
            "v": 1, "aud": "hermes-systemd-broker-v1",
            "id": secrets.token_hex(32), "approval": "staging-fixture",
            "task": "staging-fixture", "worker": "staging-worker",
            "lease_generation": 1, "job": "noop",
            "params_hash": fingerprint({"job": "noop"}),
            "iat": now, "exp": now + 60,
        }
        grant = {"claims": claims, "signature": hmac.new(
            key, _canonical(claims), hashlib.sha256).hexdigest()}
        fixture(database, claims)
        os.chown(database, identity.pw_uid, identity.pw_gid)
        os.chmod(database, 0o600)
        # Bootstrap the isolated root-owned journal before the launch lock.
        # The production journal is never opened or initialized here.
        from .fenced_unit_journal import _connect
        with _connect(journal):
            pass
        unit = unit_for_grant(claims["id"])
        try:
            result = run_staging_session(
                grant, key, journal, database,
                trusted_uid=identity.pw_uid, trusted_gid=identity.pw_gid)
            if result.get("exit_code") != 0:
                raise AssertionError("Fenced job did not succeed")
            require_recovered(journal)
            with sqlite3.connect(journal) as db:
                state = db.execute(
                    "SELECT state FROM owned_units WHERE unit=?", (unit,)
                ).fetchone()
            if state != ("verified",):
                raise AssertionError("Staging journal not verified")
            print("NEW_LAUNCHER_SIGNED_GRANT_AND_TRUSTED_PEER=PASS", flush=True)
            print("NEW_LAUNCHER_STOP_BEFORE_RELEASE=PASS", flush=True)
            print("NEW_LAUNCHER_STARTUP_GATE_AFTER_RECOVERY=PASS", flush=True)
            print("BROKER_SIGKILL_WITH_INDEPENDENT_WATCHDOG_VERIFIED=NO", flush=True)
            print("PRODUCTION_INTEGRATION_VERIFIED=NO", flush=True)
        finally:
            # Only stop an actually active fixture unit; keep the original
            # exception visible if the systemd job never started.
            from .real_systemd_crash_acceptance import active
            if active(unit):
                stop_and_verify_unit(unit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    exercise()


if __name__ == "__main__":
    main()
