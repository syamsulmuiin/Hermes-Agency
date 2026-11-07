"""Opt-in integrated staging broker SIGKILL acceptance with systemd OnFailure.

Only isolated /run/hermes-staging fixtures and randomly named test units.
Never starts, stops, reloads or modifies hermes-agency.service.
"""
import argparse
import hashlib
import hmac
import multiprocessing as mp
import os
import pwd
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time

from .broker_grants import _canonical
from .fenced_staging_broker import unit_for_grant
from .fenced_staging_launcher import run_staging_session
from .fenced_startup_gate import require_recovered
from .fenced_systemd_supervisor import stop_and_verify_unit
from .fenced_unit_journal import _connect
from .real_systemd_crash_acceptance import active, await_active, launch
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint


def ctl(*args):
    return subprocess.run(
        ["/usr/bin/systemctl", "--system", *args],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=12, check=False)


def wait_for(predicate, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(.05)
    return False


def gate_denied(journal):
    try:
        require_recovered(journal)
    except PermissionError:
        return True
    return False


def journal_state(journal, unit):
    with sqlite3.connect(journal) as db:
        row = db.execute("SELECT state FROM owned_units WHERE unit=?", (unit,)).fetchone()
    return row[0] if row else None


def broker_child(grant, key, journal, database, uid, gid, ready):
    def long_running_runner(job, fence, unit):
        if job != "noop":
            raise PermissionError("Unexpected test job")
        launch(unit)  # real transient /usr/bin/sleep 45
        await_active(unit)
        with open(ready, "x", encoding="ascii") as out:
            out.write("active")
        # Broker must be killed while its unit is active; do not return.
        while True:
            time.sleep(.1)
    run_staging_session(
        grant, key, journal, database, trusted_uid=uid,
        trusted_gid=gid, runner=long_running_runner)


def exercise():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    identity = pwd.getpwnam("nobody")
    if identity.pw_uid <= 0 or identity.pw_gid <= 0:
        raise PermissionError("Nonroot test identity required")
    base = "/run/hermes-staging"
    os.makedirs(base, mode=0o700, exist_ok=True)
    info = os.lstat(base)
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise PermissionError("Unsafe staging directory")
    os.chmod(base, 0o711)
    with tempfile.TemporaryDirectory(prefix="integrated-crash-", dir=base) as folder:
        os.chmod(folder, 0o711)
        journal = folder + "/owned.sqlite"
        trusted_dir = folder + "/trusted"
        os.mkdir(trusted_dir, 0o700)
        os.chown(trusted_dir, identity.pw_uid, identity.pw_gid)
        database = trusted_dir + "/trusted.sqlite"
        ready = folder + "/broker.ready"
        pidfile = folder + "/broker.pid"
        release = folder + "/allow.recovery"
        recovered = folder + "/recovered"
        watcher_ready = folder + "/watcher.ready"
        watcher_script = folder + "/watcher.py"
        recovery_script = folder + "/recovery.py"
        key = secrets.token_bytes(32)
        now = time.time()
        claims = {
            "v": 1, "aud": "hermes-systemd-broker-v1",
            "id": secrets.token_hex(32), "approval": "integrated-crash",
            "task": "integrated-crash", "worker": "staging-worker",
            "lease_generation": 1, "job": "noop",
            "params_hash": fingerprint({"job": "noop"}),
            "iat": now, "exp": now + 120,
        }
        grant = {"claims": claims, "signature": hmac.new(
            key, _canonical(claims), hashlib.sha256).hexdigest()}
        fixture(database, claims)
        os.chown(database, identity.pw_uid, identity.pw_gid)
        os.chmod(database, 0o600)
        with _connect(journal):
            pass
        unit = unit_for_grant(claims["id"])
        token = secrets.token_hex(8)
        watcher = "hermes-integrated-watch-" + token + ".service"
        recovery = "hermes-integrated-recover-" + token + ".service"
        wp = "/run/systemd/system/" + watcher
        rp = "/run/systemd/system/" + recovery
        python = os.path.realpath(sys.executable)
        repo = os.path.dirname(os.path.dirname(__file__))
        with open(watcher_script, "x", encoding="utf-8") as out:
            out.write(
                "import os,sys,time\n"
                "open(" + repr(watcher_ready) + ",'x').write('ready')\n"
                "while not os.path.exists(" + repr(pidfile) + "): time.sleep(.05)\n"
                "pid=int(open(" + repr(pidfile) + ").read())\n"
                "while True:\n"
                " try:\n"
                "  state=open('/proc/%d/stat'%pid).read().split(') ',1)[1].split()[0]\n"
                "  if state in ('Z','X'): sys.exit(1)\n"
                " except FileNotFoundError: sys.exit(1)\n"
                " time.sleep(.05)\n")
        with open(recovery_script, "x", encoding="utf-8") as out:
            out.write(
                "import os,sys,time\n"
                "sys.path.insert(0," + repr(repo) + ")\n"
                "while not os.path.isfile(" + repr(release) + "): time.sleep(.05)\n"
                "from agency.fenced_staging_recovery import recover_staging\n"
                "recover_staging(" + repr(journal) + ")\n"
                "open(" + repr(recovered) + ",'x').write('verified')\n")
        child = mp.get_context("fork").Process(
            target=broker_child,
            args=(grant, key, journal, database, identity.pw_uid,
                  identity.pw_gid, ready))
        installed = []
        try:
            for path, body in (
                (wp, "[Unit]\nDescription=Isolated integrated staging broker watchdog\n"
                     "OnFailure=" + recovery + "\n[Service]\nType=simple\nRestart=no\n"
                     "ExecStart=" + python + " " + watcher_script + "\n"),
                (rp, "[Unit]\nDescription=Isolated integrated staging recovery\n"
                     "[Service]\nType=oneshot\n"
                     "ExecStart=" + python + " " + recovery_script + "\n")):
                with open(path, "x", encoding="utf-8") as out:
                    out.write(body)
                os.chmod(path, 0o600)
                installed.append(path)
            if ctl("daemon-reload").returncode:
                raise RuntimeError("Isolated systemd unit reload failed")
            if ctl("start", watcher).returncode:
                raise RuntimeError("Watchdog failed to start")
            if not wait_for(lambda: os.path.isfile(watcher_ready), 10):
                raise AssertionError("Independent watcher did not start")
            child.start()
            with open(pidfile, "x", encoding="ascii") as out:
                out.write(str(child.pid))
            if not wait_for(lambda: os.path.isfile(ready), 12):
                raise AssertionError("Real staging broker did not start active unit")
            if not active(unit) or journal_state(journal, unit) != "pending":
                raise AssertionError("Unit not active with pending ownership")
            if not gate_denied(journal):
                raise AssertionError("Startup gate permitted pending launch")
            print("INTEGRATED_ACTIVE_UNIT_AND_PENDING_GATE=PASS", flush=True)
            os.kill(child.pid, signal.SIGKILL)
            child.join(5)
            if child.exitcode != -signal.SIGKILL:
                raise AssertionError("Real broker SIGKILL not confirmed")
            if not gate_denied(journal):
                raise AssertionError("Startup gate permitted broker crash")
            if not active(unit):
                raise AssertionError("Unit did not survive broker crash")
            print("INTEGRATED_REAL_BROKER_SIGKILL_GATE=PASS", flush=True)
            # Independent OnFailure recovery must wait for test release, so
            # pending-gate behavior is observed deterministically.
            if not wait_for(lambda: ctl("show", recovery,
                    "--property=ActiveState").stdout.strip() == b"ActiveState=activating", 12):
                raise AssertionError("OnFailure recovery not independently triggered")
            if not gate_denied(journal) or journal_state(journal, unit) != "pending":
                raise AssertionError("Recovery bypassed pending gate")
            print("INTEGRATED_WATCHDOG_ONFAILURE_TRIGGERED=PASS", flush=True)
            with open(release, "x", encoding="ascii") as out:
                out.write("proceed")
            if not wait_for(lambda: os.path.isfile(recovered), 15):
                raise AssertionError("Independent recovery did not finish")
            if active(unit) or journal_state(journal, unit) != "verified":
                raise AssertionError("Unit not stopped and journal not verified")
            require_recovered(journal)
            print("INTEGRATED_INDEPENDENT_RECOVERY_AND_GATE=PASS", flush=True)
            print("PRODUCTION_INTEGRATION_VERIFIED=NO", flush=True)
        finally:
            if child.is_alive():
                child.kill()
            if child.pid is not None:
                child.join(5)
            # Unblock a recovery unit before stopping it.
            if not os.path.exists(release):
                with open(release, "x", encoding="ascii") as out:
                    out.write("cleanup")
            ctl("stop", watcher)
            if os.path.isfile(journal):
                from .fenced_staging_recovery import recover_staging
                recover_staging(journal)
            ctl("stop", recovery)
            if active(unit):
                stop_and_verify_unit(unit)
            for path in installed:
                os.unlink(path)
            if installed:
                ctl("daemon-reload")
                ctl("reset-failed", watcher, recovery)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    exercise()


if __name__ == "__main__":
    main()
