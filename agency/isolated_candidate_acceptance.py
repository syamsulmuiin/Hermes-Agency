"""One-shot isolated persistent candidate acceptance. Never touches production units."""
import argparse
import hashlib
import hmac
import os
import pwd
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

from .broker_grants import _canonical
from .fenced_staging_broker import unit_for_grant
from .fenced_startup_gate import require_recovered
from .fenced_systemd_supervisor import stop_and_verify_unit
from .fenced_unit_journal import _connect
from .real_trusted_lease_ipc_test import fixture
from .real_systemd_crash_acceptance import active
from .security import fingerprint
from .signed_broker_service import submit_signed_grant
from .systemd_broker import initialize_ledger


def ctl(*args):
    return subprocess.run(("/usr/bin/systemctl", "--system", *args),
                          capture_output=True, timeout=25, check=False)


def until(fn, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(.05)
    return False


def signed(key, job):
    now = time.time()
    claims = dict(v=1, aud="hermes-systemd-broker-v1",
                  id=secrets.token_hex(32), approval=secrets.token_hex(16),
                  task=secrets.token_hex(16), worker="staging-worker",
                  lease_generation=1, job=job,
                  params_hash=fingerprint({"job": job}),
                  iat=now, exp=now+60)
    return claims, {"claims": claims, "signature": hmac.new(
        key, _canonical(claims), hashlib.sha256).hexdigest()}


def gate_denied(path):
    try:
        require_recovered(path)
    except PermissionError:
        return True
    return False


def run():
    if os.geteuid() or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and systemd required")
    identity = pwd.getpwnam("nobody")
    if identity.pw_uid <= 0 or identity.pw_gid <= 0:
        raise PermissionError("Dedicated non-root fixture identity required")
    base = "/run/hermes-staging"
    os.makedirs(base, mode=0o700, exist_ok=True)
    if os.lstat(base).st_uid != 0 or os.lstat(base).st_mode & 0o022:
        raise PermissionError("Unsafe fixture base")
    os.chmod(base, 0o711)
    repo = os.path.dirname(os.path.dirname(__file__))
    python = os.path.realpath(sys.executable)
    token = secrets.token_hex(8)
    broker_unit = "hermes-isolated-candidate-" + token + ".service"
    recovery_unit = "hermes-isolated-recovery-" + token + ".service"
    bp = "/run/systemd/system/" + broker_unit
    rp = "/run/systemd/system/" + recovery_unit
    installed = []
    with tempfile.TemporaryDirectory(prefix="candidate-", dir=base) as folder:
        os.chmod(folder, 0o711)
        sockdir = folder + "/socket"
        os.mkdir(sockdir, 0o710)
        os.chown(sockdir, 0, identity.pw_gid)
        sock = sockdir + "/candidate.sock"
        rootdir = folder + "/root"
        os.mkdir(rootdir, 0o700)
        ledger = rootdir + "/ledger.sqlite"
        journal = rootdir + "/owned.sqlite"
        keydir = folder + "/key"
        os.mkdir(keydir, 0o700)
        keypath = keydir + "/signing.key"
        trusted_dir = folder + "/trusted"
        os.mkdir(trusted_dir, 0o700)
        os.chown(trusted_dir, identity.pw_uid, identity.pw_gid)
        dbpath = trusted_dir + "/agency.sqlite"
        marker = folder + "/allow-hold-test"
        if os.path.lexists(marker):
            raise PermissionError("Shared test hold marker already exists")
        key = secrets.token_bytes(64)
        with open(keypath, "xb") as out:
            out.write(key)
        os.chown(keypath, 0, identity.pw_gid)
        os.chmod(keypath, 0o640)
        initialize_ledger(ledger)
        with _connect(journal):
            pass
        c1, g1 = signed(key, "noop")
        c2, g2 = signed(key, "identity")
        fixture(dbpath, c1)
        # The fixture schema is shared; append a second live lease.
        with sqlite3.connect(dbpath) as db:
            db.execute("INSERT INTO tasks VALUES (?,'in_progress','developer')", (c2["task"],))
            db.execute("INSERT INTO task_leases VALUES (?,?,?,?)",
                       (c2["task"], c2["worker"], 1, time.time()+180))
            db.execute("INSERT INTO approvals VALUES (?,'consumed')", (c2["approval"],))
            db.execute("INSERT INTO execution_grants VALUES (?,?,?,?,?,?,?)",
                       (c2["id"],c2["task"],c2["approval"],c2["worker"],1,
                        "execute_shell",c2["params_hash"]))
        os.chown(dbpath, identity.pw_uid, identity.pw_gid)
        os.chmod(dbpath, 0o600)
        with open(marker, "x") as out:
            out.write(token)
        broker_command = (python + " -m agency.fenced_broker_candidate"
                          + " --socket " + sock + " --trusted-user nobody"
                          + " --ledger " + ledger + " --journal " + journal
                          + " --trusted-db " + dbpath + " --key " + keypath
                          + " --execute --isolated-test")
        recovery_command = (python + " -m agency.fenced_owned_recovery"
                            + " --journal " + journal + " --execute")
        try:
            for path, body in (
                (rp, "[Unit]\nDescription=Isolated candidate recovery\n"
                     "[Service]\nType=oneshot\nUser=root\n"
                     "WorkingDirectory=" + repo + "\nExecStart=" + recovery_command + "\n"),
                (bp, "[Unit]\nDescription=Isolated persistent fenced candidate\n"
                     "After=" + recovery_unit + "\nRequires=" + recovery_unit
                     + "\nOnFailure=" + recovery_unit
                     + "\n[Service]\nType=simple\nUser=root\n"
                     "WorkingDirectory=" + repo + "\nEnvironment=HERMES_ISOLATED_HOLD_MARKER=" + marker + "\nExecStartPre=" + python
                     + " -m agency.fenced_startup_gate --journal " + journal
                     + "\nExecStart=" + broker_command
                     + "\nExecStopPost=" + recovery_command
                     + "\nRestart=no\nTimeoutStopSec=20\n")):
                with open(path, "x") as out:
                    out.write(body)
                installed.append(path)
            if ctl("daemon-reload").returncode or ctl("start", broker_unit).returncode:
                raise AssertionError("Candidate service failed to start")
            if not until(lambda: os.path.exists(sock), 10):
                raise AssertionError("Candidate socket not ready")
            print("CANDIDATE_SYSTEMD_SOCKET=PASS", flush=True)
            # SO_PEERCRED requires the dedicated nonroot UID. Fork and drop
            # privileges in a child; never weaken candidate peer checking.
            def request(grant):
                # The peer must run as trusted UID; send only sanitized
                # error class back to the root acceptance parent.
                read_fd, write_fd = os.pipe()
                pid = os.fork()
                if pid == 0:
                    os.close(read_fd)
                    try:
                        os.setgroups([])
                        os.setgid(identity.pw_gid)
                        os.setuid(identity.pw_uid)
                        response = submit_signed_grant(sock, grant)
                        status = 0 if response.get("exit_code") == 0 else 2
                        os.write(write_fd, ("reply=" + str(response.get("exit_code", "missing"))).encode()[:128])
                        os._exit(status)
                    except BaseException as exc:
                        os.write(write_fd, ("error=" + type(exc).__name__).encode())
                        os._exit(3)
                os.close(write_fd)
                detail = os.read(read_fd, 256).decode("ascii", "replace")
                os.close(read_fd)
                _, status = os.waitpid(pid, 0)
                return os.waitstatus_to_exitcode(status), detail
            first_status, first_detail = request(g1)
            if first_status != 0:
                diagnostics = ctl("status", broker_unit, "--no-pager", "-l")
                print("CANDIDATE_FIRST_GRANT_DIAGNOSTIC=" + first_detail, flush=True)
                print(diagnostics.stdout.decode("utf-8", "replace")[-4000:], flush=True)
                raise AssertionError("Valid signed grant failed: " + first_detail)
            print("CANDIDATE_SIGNED_GRANT=PASS", flush=True)
            if request(g1)[0] == 0:
                raise AssertionError("Consumed grant replay succeeded")
            print("CANDIDATE_REPLAY_DENIED=PASS", flush=True)
            pid = os.fork()
            if pid == 0:
                try:
                    os.setgroups([])
                    os.setgid(identity.pw_gid)
                    os.setuid(identity.pw_uid)
                    submit_signed_grant(sock, g2)
                except BaseException:
                    pass
                os._exit(0)
            unit = unit_for_grant(c2["id"])
            if not until(lambda: active(unit), 15):
                raise AssertionError("Hold unit never became active")
            contender = sqlite3.connect(dbpath, timeout=.2, isolation_level=None)
            try:
                try:
                    contender.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    print("CANDIDATE_TRUSTED_LEASE_LOCKED=PASS", flush=True)
                else:
                    contender.rollback()
                    raise AssertionError("Trusted lease was not locked")
            finally:
                contender.close()
            mainpid = int(ctl("show", broker_unit, "--property=MainPID",
                              "--value").stdout.strip())
            if mainpid <= 1:
                raise AssertionError("Invalid candidate PID")
            os.kill(mainpid, signal.SIGKILL)
            if not gate_denied(journal):
                raise AssertionError("Pending gate opened after SIGKILL")
            print("CANDIDATE_SIGKILL_PENDING_GATE=PASS", flush=True)
            if not until(lambda: not active(unit) and not gate_denied(journal), 25):
                raise AssertionError("Independent candidate recovery not verified")
            print("CANDIDATE_SYSTEMD_RECOVERY=PASS", flush=True)
            if ctl("start", broker_unit).returncode:
                raise AssertionError("Candidate restart after recovery failed")
            if not until(lambda: os.path.exists(sock), 10):
                raise AssertionError("Candidate restart socket absent")
            print("CANDIDATE_RESTART_AFTER_RECOVERY=PASS", flush=True)
            print("PERSISTENT_CANDIDATE_ISOLATED_E2E=PASS", flush=True)
        finally:
            ctl("stop", broker_unit)
            if os.path.isfile(journal):
                from .fenced_owned_recovery import recover_owned_journal
                recover_owned_journal(journal)
            ctl("stop", recovery_unit)
            for path in installed:
                os.unlink(path)
            if installed:
                ctl("daemon-reload")
                ctl("reset-failed", broker_unit, recovery_unit)
            if os.path.exists(marker):
                os.unlink(marker)
            if 'pid' in locals():
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass
    for name in ("hermes-agency.service", "hermes-signed-broker.service"):
        if ctl("is-active", name).stdout.strip() != b"active":
            raise AssertionError("Production service not active: " + name)
        print("PRODUCTION_UNCHANGED_ACTIVE=" + name, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__ == "__main__":
    main()
