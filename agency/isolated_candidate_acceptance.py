"""One-shot isolated persistent candidate acceptance. Never touches production units."""
import argparse
import json
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

from .broker_grants import issue_broker_grant
from .operator_auth import LocalOperatorGate
from .security import SecureAgencyStore
from .trusted import TrustedApprovalService
from .fenced_staging_broker import unit_for_grant
from .fenced_startup_gate import require_recovered
from .fenced_systemd_supervisor import stop_and_verify_unit
from .fenced_unit_journal import _connect
from .real_systemd_crash_acceptance import active
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


def real_operator_grants(dbpath, keypath, identity):
    """Create approved grants inside a disposable non-root staging process."""
    # Import before setuid: checkout may be under /root, inaccessible to nobody.
    from pathlib import Path
    from .trusted_broker_adapter import _trusted_key
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            os.setgroups([])
            os.setgid(identity.pw_gid)
            os.setuid(identity.pw_uid)
            store = SecureAgencyStore(Path(dbpath))
            service = TrustedApprovalService(store, secrets.token_bytes(32))
            operator_secret = secrets.token_bytes(32)
            salt, verifier = LocalOperatorGate.provision(operator_secret)
            gate = LocalOperatorGate(service, "staging-operator", salt, verifier)
            key = _trusted_key(keypath)
            envelopes = []
            for job in ("noop", "identity"):
                task = store.create_task("Isolated operator staging", "developer")
                approval = store.request_approval(
                    task, "execute_shell", {"job": job}, "developer")
                lease = store.claim(task, "staging-worker", ttl=180)
                worker = service.issue_credential("staging-worker", "worker")
                try:
                    gate.authenticate(b"invalid-staging-operator-secret")
                except PermissionError:
                    pass
                else:
                    raise AssertionError("Wrong operator secret accepted")
                service.decide(approval, gate.authenticate(operator_secret), True)
                envelopes.append(issue_broker_grant(
                    service, approval, task, job, worker, lease, key, ttl=60))
            store.close()
            os.write(write_fd, json.dumps(envelopes).encode())
            os._exit(0)
        except BaseException as exc:
            os.write(write_fd, ("ERROR:" + type(exc).__name__ + ":" + str(exc)).encode()[:1024])
            os._exit(1)
    os.close(write_fd)
    with os.fdopen(read_fd, "rb") as pipe:
        payload = pipe.read(16384)
    _, status = os.waitpid(pid, 0)
    if os.waitstatus_to_exitcode(status) != 0:
        raise AssertionError("Trusted operator grant setup failed: " +
                             payload.decode("utf-8", "replace"))
    envelopes = json.loads(payload)
    if len(envelopes) != 2:
        raise AssertionError("Expected two real operator grants")
    return [(envelope["claims"], envelope) for envelope in envelopes]


def gate_denied(path):
    try:
        require_recovered(path)
    except PermissionError:
        return True
    return False


def run(*, deployed=None):
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
    sandbox = ''
    if deployed is not None:
        import re
        from pathlib import Path
        repo = str(Path(deployed).resolve(strict=True))
        if not re.fullmatch(r'/opt/hermes-fenced-[0-9a-f]{12}', repo):
            raise PermissionError('Pinned /opt candidate deployment required')
        if not Path(repo, 'agency/fenced_broker_candidate.py').is_file():
            raise PermissionError('Candidate module missing')
        sandbox = ('NoNewPrivileges=yes\nProtectSystem=strict\n'
                   'ReadWritePaths=/run/hermes-staging\n'
                   'ProtectHome=yes\nPrivateTmp=yes\n')
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
        os.mkdir(keydir, 0o711)
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
        (c1, g1), (c2, g2) = real_operator_grants(
            dbpath, keypath, identity)
        print("CANDIDATE_REAL_OPERATOR_APPROVAL=PASS", flush=True)
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
                     "WorkingDirectory=" + repo + "\n" + sandbox + "ExecStart=" + recovery_command + "\n"),
                (bp, "[Unit]\nDescription=Isolated persistent fenced candidate\n"
                     "After=" + recovery_unit + "\nRequires=" + recovery_unit
                     + "\nOnFailure=" + recovery_unit
                     + "\n[Service]\nType=simple\nUser=root\n"
                     "WorkingDirectory=" + repo + "\n" + sandbox + "Environment=HERMES_ISOLATED_HOLD_MARKER=" + marker + "\nExecStartPre=" + python
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
            if deployed is not None:
                properties = ("NoNewPrivileges", "ProtectSystem", "ProtectHome",
                              "PrivateTmp", "ReadWritePaths", "WorkingDirectory")
                for name in (broker_unit, recovery_unit):
                    values = {}
                    for prop in properties:
                        result = ctl("show", name, "--property=" + prop, "--value")
                        if result.returncode:
                            raise AssertionError("Cannot inspect effective systemd " + prop)
                        values[prop] = result.stdout.decode("utf-8", "replace").strip()
                    if (values["NoNewPrivileges"] != "yes"
                            or values["ProtectSystem"] != "strict"
                            or values["ProtectHome"] != "yes"
                            or values["PrivateTmp"] != "yes"
                            or values["WorkingDirectory"] != repo
                            or base not in values["ReadWritePaths"]):
                        raise AssertionError("Effective staging sandbox mismatch: " + name
                                             + " " + repr(values))
                print("CANDIDATE_EFFECTIVE_SYSTEMD_SANDBOX=PASS", flush=True)

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
            def crash_and_recover(unit, sidecar_origin=False):
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
                if sidecar_origin:
                    print("SIDECAR_HOLD_SIGKILL_RECOVERY=PASS", flush=True)
            # Pinned candidate: the held job must originate from the real
            # operator IPC, not a separately pre-signed direct broker grant.
            if deployed is not None:
                def sidecar_hold(operator_socket, hold_request):
                    child = os.fork()
                    if child == 0:
                        try:
                            from .isolated_operator_ipc import request_operator
                            request_operator(operator_socket, hold_request)
                        except BaseException:
                            pass  # SIGKILL intentionally interrupts this IPC.
                        os._exit(0)
                    sidecar_children.append(child)
                    print("SIDECAR_HOLD_REQUEST_SUBMITTED=PASS", flush=True)

                from .isolated_sidecar_rehearsal import run_sidecar_rehearsal
                sidecar_children = []
                # Crash and recovery are executed while the real sidecar is
                # still serving the hold request, via callback below.
                # Unit identity derives from the signed grant ID, NOT task ID.
                # Resolve the running unit by its staging journal instead.
                def sidecar_crash(operator_socket, hold_request):
                    sidecar_hold(operator_socket, hold_request)
                    def pending_units():
                        with sqlite3.connect(journal) as connection:
                            return [row[0] for row in connection.execute(
                                "SELECT unit FROM owned_units WHERE state='pending'")]
                    if not until(lambda: len(pending_units()) == 1, 15):
                        raise AssertionError("Sidecar pending hold not journaled uniquely")
                    pending = pending_units()
                    if not until(lambda: active(pending[0]), 15):
                        raise AssertionError("Sidecar-originated hold unit not active")
                    print("SIDECAR_HOLD_UNIT_ACTIVE=PASS", flush=True)
                    crash_and_recover(pending[0], sidecar_origin=True)
                run_sidecar_rehearsal(folder, dbpath, keypath, sock,
                                     identity, repo, hold_callback=sidecar_crash)
            else:
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
                    print("CANDIDATE_HOLD_UNIT=" + unit, flush=True)
                    print("CANDIDATE_HOLD_UNIT_STATUS=" + ctl("status", unit, "--no-pager", "-l").stdout.decode("utf-8", "replace")[-3500:], flush=True)
                    print("CANDIDATE_HOLD_BROKER_STATUS=" + ctl("status", broker_unit, "--no-pager", "-l").stdout.decode("utf-8", "replace")[-4500:], flush=True)
                    print("CANDIDATE_HOLD_JOURNAL=" + repr(sqlite3.connect(journal).execute("SELECT unit,state FROM owned_units").fetchall()), flush=True)
                    print("CANDIDATE_HOLD_LEDGER=" + repr(sqlite3.connect(ledger).execute("SELECT grant_id,status FROM signed_grant_consumptions").fetchall()), flush=True)
                    raise AssertionError("Hold unit never became active")
                crash_and_recover(unit)
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
    # Disposable-unit rollback: no candidate unit files remain installed.
    if any(os.path.lexists(path) for path in (bp, rp)):
        raise AssertionError("Disposable staging units not removed")
    if ctl("is-enabled", broker_unit).stdout.strip() == b"enabled":
        raise AssertionError("Disposable broker unexpectedly enabled")
    print("CANDIDATE_DISPOSABLE_ROLLBACK=PASS", flush=True)
    for name in ("hermes-agency.service", "hermes-signed-broker.service"):
        if ctl("is-active", name).stdout.strip() != b"active":
            raise AssertionError("Production service not active: " + name)
        print("PRODUCTION_UNCHANGED_ACTIVE=" + name, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--deployed", default=None, help="Pinned /opt candidate enables real sandbox directives")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run(deployed=args.deployed)


if __name__ == "__main__":
    main()
