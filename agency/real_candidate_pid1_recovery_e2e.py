"""Opt-in PID1 OnFailure acceptance for the actual isolated fenced broker.

No production unit is stopped or reconfigured. All fixtures live in /run/hermes-staging.
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
from .fenced_staging_broker import unit_for_grant
from .real_candidate_socket_replay_e2e import BASE, CLIENT
from .real_systemd_crash_acceptance import active
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint
from .signed_broker_service import provision_broker_key
from .systemd_broker import initialize_ledger
from .fenced_systemd_supervisor import stop_and_verify_unit


def ctl(*args):
    return subprocess.run(["/usr/bin/systemctl", "--system", *args],
                          capture_output=True, text=True, timeout=15, check=False)


def wait_for(predicate, message, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError(message)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and PID1 systemd required")
    ident = pwd.getpwnam("nobody")
    if ident.pw_uid <= 0 or ident.pw_gid <= 0:
        raise PermissionError("Non-root trusted identity required")
    if not os.path.isdir(BASE):
        os.mkdir(BASE, 0o711)
    st = os.stat(BASE)
    if st.st_uid != 0 or st.st_mode & 0o022 or not st.st_mode & 0o001:
        raise PermissionError("Unsafe or inaccessible staging base")
    tag = secrets.token_hex(8)
    folder = BASE + "/pid1-e2e-" + tag
    os.mkdir(folder, 0o710)
    os.chown(folder, 0, ident.pw_gid)
    sock, ledger, journal, database, keyfile, marker = (
        folder + "/" + n for n in ("broker.sock", "ledger.sqlite",
        "journal.sqlite", "trusted.sqlite", "broker.key", "hold.marker"))
    broker_name = "hermes-pid1-broker-" + tag + ".service"
    recovery_name = "hermes-pid1-recovery-" + tag + ".service"
    broker_file = "/run/systemd/system/" + broker_name
    recovery_file = "/run/systemd/system/" + recovery_name
    unit = None
    client = None
    installed = False
    try:
        initialize_ledger(ledger)
        from .fenced_unit_journal import recover_owned_units
        recover_owned_units(journal)
        provision_broker_key(keyfile, ident.pw_gid)
        with open(keyfile, "rb") as inp:
            key = inp.read()
        now = time.time()
        claims = {"v":1, "aud":"hermes-systemd-broker-v1",
                  "id":secrets.token_hex(32), "approval":"test-approval",
                  "task":"test-task", "worker":"test-worker",
                  "lease_generation":1, "job":"identity",
                  "params_hash":fingerprint({"job":"identity"}),
                  "iat":now, "exp":now+55}
        grant = {"claims":claims,"signature":
                 hmac.new(key,_canonical(claims),hashlib.sha256).hexdigest()}
        fixture(database, claims)
        os.chown(database, ident.pw_uid, ident.pw_gid)
        os.chmod(database, 0o600)
        with open(marker, "x", encoding="ascii") as out:
            out.write("isolated")
        unit = unit_for_grant(claims["id"])
        repo = os.path.dirname(os.path.dirname(__file__))
        python = sys.executable
        recovery_script = folder + "/recover.py"
        with open(recovery_script, "x", encoding="utf-8") as out:
            out.write("import sys\nsys.path.insert(0," + repr(repo) +
                      ")\nfrom agency.fenced_unit_journal import recover_owned_units\n"
                      "recover_owned_units(" + repr(journal) + ")\n")
        broker_cmd = " ".join((python, "-m", "agency.fenced_broker_candidate",
            "--socket", sock, "--trusted-user", ident.pw_name,
            "--ledger", ledger, "--journal", journal,
            "--trusted-db", database, "--key", keyfile,
            "--execute", "--isolated-test"))
        broker_config = ("[Unit]\nDescription=Isolated real candidate broker PID1 test\n"
                         "OnFailure=" + recovery_name + "\n"
                         "[Service]\nType=simple\nRestart=no\n"
                         "WorkingDirectory=" + repo + "\n"
                         "Environment=PYTHONDONTWRITEBYTECODE=1\n"
                         "Environment=HERMES_ISOLATED_HOLD_MARKER=" + marker + "\n"
                         "ExecStart=" + broker_cmd + "\n")
        recovery_config = ("[Unit]\nDescription=Isolated real candidate recovery\n"
                           "[Service]\nType=oneshot\n"
                           "Environment=PYTHONDONTWRITEBYTECODE=1\n"
                           "ExecStart=" + python + " " + recovery_script + "\n")
        for path, data in ((broker_file, broker_config),
                           (recovery_file, recovery_config)):
            with open(path, "x", encoding="utf-8") as out:
                out.write(data)
            os.chmod(path, 0o600)
        installed = True
        if ctl("daemon-reload").returncode or ctl("start", broker_name).returncode:
            raise AssertionError("Isolated candidate service start failed")
        wait_for(lambda: os.path.exists(sock), "Candidate socket not ready")
        request = json.dumps({"grant":grant},separators=(",",":"))
        client = subprocess.Popen(
            [python, "-c", CLIENT, sock, request],
            preexec_fn=lambda: (os.setgroups([]), os.setgid(ident.pw_gid),
                                 os.setuid(ident.pw_uid)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def running():
            with sqlite3.connect(ledger) as db:
                try:
                    row = db.execute(
                        "SELECT status FROM signed_grant_consumptions WHERE grant_id=?",
                        (claims["id"],)).fetchone()
                except sqlite3.OperationalError as exc:
                    if "no such table: signed_grant_consumptions" not in str(exc):
                        raise
                    return False
            return row == ("started",) and active(unit)
        wait_for(running, "Real signed job not active before crash")
        print("PID1_REAL_BROKER_ACTIVE_SIGNED_JOB=PASS", flush=True)
        if ctl("kill", "--signal=SIGKILL", "--kill-who=main", broker_name).returncode:
            raise AssertionError("PID1 broker SIGKILL failed")
        # OnFailure must independently recover the owned unit.
        def recovered():
            with sqlite3.connect(journal) as db:
                row = db.execute(
                    "SELECT state FROM owned_units WHERE unit=?", (unit,)).fetchone()
            return row == ("verified",) and not active(unit)
        wait_for(recovered, "PID1 OnFailure failed to stop and verify job", 20)
        require_recovered(journal)
        print("PID1_REAL_BROKER_ONFAILURE_RECOVERY=PASS", flush=True)
        if client is not None:
            client.communicate(timeout=10)
            client = None
        with sqlite3.connect(ledger) as db:
            row = db.execute(
                "SELECT status FROM signed_grant_consumptions WHERE grant_id=?",
                (claims["id"],)).fetchone()
        if row != ("started",):
            raise AssertionError("Crash grant lost or unexpectedly modified")
        # Ensure the actual broker service restarts only after recovery.
        if os.path.lexists(sock):
            os.unlink(sock)
        ctl("reset-failed", broker_name)
        if ctl("start", broker_name).returncode:
            raise AssertionError("Recovered broker restart failed")
        wait_for(lambda: os.path.exists(sock), "Restarted candidate socket absent")
        replay = subprocess.run(
            [python, "-c", CLIENT, sock, request],
            preexec_fn=lambda: (os.setgroups([]), os.setgid(ident.pw_gid),
                                 os.setuid(ident.pw_uid)),
            capture_output=True, text=True, timeout=20, check=False)
        if replay.returncode or replay.stdout.strip() != "DENIED_NO_REPLY":
            raise AssertionError("Replay accepted after PID1 recovery: " + replay.stdout)
        with sqlite3.connect(ledger) as db:
            rows = db.execute(
                "SELECT status FROM signed_grant_consumptions WHERE grant_id=?",
                (claims["id"],)).fetchall()
        if rows != [("started",)]:
            raise AssertionError("Durable replay ledger changed")
        print("PID1_REAL_BROKER_RESTART_REPLAY_DENIED=PASS", flush=True)
        print("PID1_REAL_BROKER_FULL_E2E=PASS", flush=True)
        print("PRODUCTION_CUTOVER_GO=NO", flush=True)
    finally:
        if client is not None and client.poll() is None:
            client.kill()
            client.communicate(timeout=10)
        if installed:
            ctl("stop", broker_name)
            ctl("stop", recovery_name)
        if unit is not None and active(unit):
            stop_and_verify_unit(unit)
        for path in (broker_file, recovery_file):
            if os.path.exists(path):
                os.unlink(path)
        if installed:
            ctl("daemon-reload")
            ctl("reset-failed", broker_name, recovery_name)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.parse_args(argv)
    run()


if __name__ == "__main__":
    main()
