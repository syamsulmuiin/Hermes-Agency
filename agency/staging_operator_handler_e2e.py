"""Real operator-handler staging acceptance; never uses production resources.

Requires root to create the root-owned admission lock and connect as the
authorized local peer. The listener drops privileges to nobody.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import sys
import tempfile
import time

from .operator_control import serve_operator_forever

CHILD = """
import os,sys
from agency.operator_control import serve_operator_forever
class Boundary:
 def approve_operator_request(self,*args):
  with open(sys.argv[5],'w') as f: f.write('STAGING_ONLY')
  raise PermissionError('No real approval permitted')
 def execute_operator_approved_job(self,*args):
  raise AssertionError('Broker execution forbidden')
def factory(): return Boundary(),lambda:None
serve_operator_forever(sys.argv[1],factory,('dummy',b'0'*16,b'0'*32),
 '/nonexistent/staging-broker.key','/nonexistent/staging-broker.sock',
 lambda:False,admission_lock=sys.argv[2],freeze_marker=sys.argv[3])
"""

def request(sock):
    message = {"action":"approve", "approval_id":"staging-only",
               "operator_secret_hex":"0"*64}
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(str(sock))
        client.sendall((json.dumps(message)+"\n").encode())
        data = client.recv(256)
    if json.loads(data).get("status") != "denied":
        raise AssertionError("Staging request not denied")

def wait_socket(sock, child):
    for _ in range(100):
        if sock.exists():
            return
        if child.poll() is not None:
            raise AssertionError("Staging sidecar exited early")
        time.sleep(.05)
    raise TimeoutError("Staging socket missing")

def exercise():
    if os.geteuid()!=0:
        raise PermissionError("Root required for isolated root-owned lock and peer")
    identity=pwd.getpwnam("nobody")
    if identity.pw_uid==0:
        raise PermissionError("Non-root staging identity required")
    with tempfile.TemporaryDirectory(prefix="hermes-operator-e2e-") as temp:
        root=Path(temp)
        root.chmod(0o711)
        # Socket parent must be 0700 and owned by listener identity.
        directory=root/"socket"
        directory.mkdir(mode=0o700)
        os.chown(directory,identity.pw_uid,identity.pw_gid)
        sock=directory/"operator.sock"
        lock=root/"admission.lock"
        lock.touch(mode=0o640)
        lock.chmod(0o640)
        freeze=root/"admission.freeze"
        marker=directory/"boundary-attempt"
        child=subprocess.Popen(
            [sys.executable,"-u","-c",CHILD,str(sock),str(lock),str(freeze),str(root),str(marker)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
            preexec_fn=lambda:(os.setgroups([]),os.setgid(identity.pw_gid),
                               os.setuid(identity.pw_uid)))
        try:
            wait_socket(sock,child)
            fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                request(sock)
                if marker.exists():
                    raise AssertionError("Boundary reached during exclusive drain")
            finally:
                fcntl.flock(fd,fcntl.LOCK_UN)
                os.close(fd)
            freeze.touch(mode=0o600)
            request(sock)
            if marker.exists():
                raise AssertionError("Boundary reached during freeze")
            freeze.unlink()
            # The fake boundary always rejects; no real approval can succeed.
            # Its invocation confirms the handler acquired and released its
            # shared lease before reaching the boundary.
            request(sock)
            if not marker.exists() or marker.read_text()!="STAGING_ONLY":
                raise AssertionError("Shared admission did not reach staging boundary")
            return {"real_operator_handler":"PASS",
                    "exclusive_lock_denial":"PASS","freeze_denial":"PASS",
                    "shared_lock_handler_path":"PASS",
                    "real_approval":False,"broker_execution":False,
                    "production_mutated":False,"cutover_authorized":False}
        finally:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            child.stderr.close()

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--isolated",action="store_true",required=True)
    parser.parse_args(argv)
    try:
        result=exercise()
    except (OSError,ValueError,PermissionError,AssertionError,TimeoutError) as exc:
        print("STAGING_OPERATOR_E2E=FAIL")
        print("ERROR="+type(exc).__name__)
        print("PRODUCTION_CUTOVER_GO=NO")
        return 2
    print(json.dumps(result,sort_keys=True))
    print("STAGING_OPERATOR_E2E=PASS")
    print("PRODUCTION_CUTOVER_GO=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
