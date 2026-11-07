"""Real trusted-sidecar SIGKILL with independent systemd recovery acceptance.

The root test coordinator is NOT the recovery authority: a separate systemd
OnFailure service stops/verifies the journaled real transient unit.
This test deliberately proves SQLite lock can release before unit stops.
"""
import argparse
import hashlib
import hmac
import json
import multiprocessing as mp
import os
import pwd
import secrets
import socket
import sqlite3
import tempfile
import time

from .broker_grants import _canonical
from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import register_before_launch
from .real_systemd_auto_recovery_test import ctl
from .real_systemd_crash_acceptance import active, await_active, launch
from .fenced_systemd_supervisor import stop_and_verify_unit
from .real_trusted_lease_ipc_test import fixture
from .security import fingerprint


def trusted_child(conn, database, key, uid, inherited_parent):
    inherited_parent.close()
    from .trusted_lease_ipc import serve_fence_connection
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
    serve_fence_connection(conn, database, key,
                           cleanup_before_release=lambda claims: None)


def run():
    if os.geteuid() != 0 or not os.path.isdir("/run/systemd/system"):
        raise PermissionError("Root and real systemd required")
    uid = pwd.getpwnam("nobody").pw_uid
    if uid == 0:
        raise PermissionError("Non-root trusted UID required")
    ident = secrets.token_hex(8)
    watched = "hermes-real-sidecar-watch-" + ident + ".service"
    recovery = "hermes-real-sidecar-recover-" + ident + ".service"
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    with tempfile.TemporaryDirectory(prefix="hermes-real-sidecar-",dir="/run") as folder:
        os.chmod(folder,0o711)
        journal = folder + "/owned.sqlite"
        database = folder + "/trusted.sqlite"
        ready = folder + "/ready"
        pidfile = folder + "/sidecar.pid"
        worker = folder + "/watch.py"
        recover = folder + "/recover.py"
        repo = os.path.dirname(os.path.dirname(__file__))
        python = os.path.realpath(__import__("sys").executable)
        key = secrets.token_bytes(32)
        now = time.time()
        claims = {"v":1,"aud":"hermes-systemd-broker-v1",
                  "id":secrets.token_hex(32),"approval":"test-approval",
                  "task":"test-task","worker":"test-worker",
                  "lease_generation":1,"job":"noop",
                  "params_hash":fingerprint({"job":"noop"}),
                  "iat":now,"exp":now+60}
        grant = {"claims":claims,"signature":
                 hmac.new(key,_canonical(claims),hashlib.sha256).hexdigest()}
        fixture(database,claims)
        os.chown(database,uid,uid)
        os.chmod(database,0o600)
        # Recovery is systemd-owned; coordinator SIGKILL is not required for
        # recovery and cannot mark journal verified itself.
        with open(worker,"w",encoding="utf-8") as f:
            f.write("import sys,time\nsys.path.insert(0,"+repr(repo)+")\n"
                    "open("+repr(ready)+",'x').write('ready')\n"
                    "while True: time.sleep(1)\n")
        with open(recover,"w",encoding="utf-8") as f:
            f.write("import sys\nsys.path.insert(0,"+repr(repo)+")\n"
                    "from agency.fenced_unit_journal import recover_owned_units\n"
                    "recover_owned_units("+repr(journal)+")\n")
        wp="/run/systemd/system/"+watched
        rp="/run/systemd/system/"+recovery
        watch_text=("[Unit]\nDescription=Isolated real-sidecar crash watch\n"
                    "OnFailure="+recovery+"\n[Service]\nType=simple\nRestart=no\n"
                    "ExecStart="+python+" "+worker+"\n")
        recover_text=("[Unit]\nDescription=Isolated real-sidecar recovery\n"
                      "[Service]\nType=oneshot\nExecStart="+python+" "+recover+"\n")
        parent, peer = socket.socketpair()
        child = mp.Process(target=trusted_child,args=(peer,database,key,uid,parent))
        try:
            for path,body in ((wp,watch_text),(rp,recover_text)):
                with open(path,"x",encoding="utf-8") as f:
                    f.write(body)
                os.chmod(path,0o600)
            if ctl("daemon-reload").returncode:
                raise RuntimeError("systemd reload failed")
            register_before_launch(journal,unit)
            launch(unit)
            await_active(unit)
            if ctl("start",watched).returncode:
                raise RuntimeError("Watcher failed to start")
            deadline=time.monotonic()+10
            while time.monotonic()<deadline and not os.path.isfile(ready):
                time.sleep(.05)
            if not os.path.isfile(ready):
                raise RuntimeError("Watcher not ready")
            child.start()
            with open(pidfile,"x",encoding="ascii") as f:
                f.write(str(child.pid))
            peer.close()
            from .trusted_lease_ipc import _send,_read_line
            parent.settimeout(8)
            _send(parent,{"grant":grant})
            if json.loads(_read_line(parent)) != {"status":"locked","grant_id":claims["id"]}:
                raise AssertionError("Trusted sidecar failed to acquire lock")
            started=time.monotonic()
            child.kill()
            child.join(5)
            if child.exitcode is None:
                raise AssertionError("Trusted sidecar not terminated")
            unlocked=None
            with sqlite3.connect(database,timeout=.2,isolation_level=None) as db:
                db.execute("BEGIN IMMEDIATE")
                unlocked=time.monotonic()
                db.rollback()
            print("real_sidecar_sigkill_sqlite_unlock_delay_ms="+str(round((unlocked-started)*1000)),flush=True)
            if not active(unit):
                raise AssertionError("Unit unexpectedly stopped before independent recovery test")
            try:
                require_recovered(journal)
            except PermissionError:
                print("real_sidecar_sigkill_pending_gate=PASS",flush=True)
            else:
                raise AssertionError("Unlocked lease bypassed pending journal")
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                with sqlite3.connect(journal) as db:
                    row=db.execute("SELECT state FROM owned_units WHERE unit=?",(unit,)).fetchone()
                if row==("verified",) and not active(unit):
                    stopped=time.monotonic()
                    require_recovered(journal)
                    print("real_sidecar_sigkill_systemd_recovery_delay_ms="+str(round((stopped-started)*1000)),flush=True)
                    print("real_sidecar_sigkill_independent_recovery=PASS",flush=True)
                    return
                time.sleep(.1)
            raise AssertionError("Independent recovery failed after real sidecar SIGKILL")
        finally:
            parent.close()
            peer.close()
            if child.is_alive():
                child.kill()
            if child.pid is not None:
                child.join(3)
            ctl("stop",watched)
            ctl("stop",recovery)
            if active(unit):
                stop_and_verify_unit(unit)
            for path in (wp,rp):
                if os.path.exists(path):
                    os.unlink(path)
            ctl("daemon-reload")
            ctl("reset-failed",watched,recovery)


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run()


if __name__=="__main__":
    main()
