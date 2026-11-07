"""Isolated real Unix-socket sidecar listener restart/freeze acceptance.

Uses a disposable root-owned fixture, a non-root child and root IPC client.
Never reads production secrets or touches production sockets or systemd units.
"""
import json
import os
import pwd
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest


CHILD = """
import signal, sys
from agency.operator_control import serve_operator_forever
class Boundary:
    def approve_operator_request(self, *args):
        return None
    def execute_operator_approved_job(self, *args):
        raise AssertionError("Execution not expected")
stop = [False]
signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__(0, True))
serve_operator_forever(
    sys.argv[1], lambda: (Boundary(), lambda: None),
    ("test", b"s"*16, b"v"*32), "/unused/key", "/unused/broker",
    lambda: stop[0], admission_lock=sys.argv[2], freeze_marker=sys.argv[3])
"""


@unittest.skipUnless(os.geteuid() == 0, "Root peer and root-owned lock required")
class RealSidecarFreezeStagingTests(unittest.TestCase):
    def test_socket_denied_across_real_listener_restart(self):
        identity = pwd.getpwnam("nobody")
        with tempfile.TemporaryDirectory(prefix="hermes-operator-e2e-") as folder:
            os.chmod(folder, 0o711)
            lock = os.path.join(folder, "admission.lock")
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
            os.close(fd)
            os.chown(lock, 0, identity.pw_gid)
            os.chmod(lock, 0o640)
            freeze = os.path.join(folder, "admission.freeze")
            sockdir = os.path.join(folder, "operator")
            os.mkdir(sockdir, 0o700)
            os.chown(sockdir, identity.pw_uid, identity.pw_gid)
            path = os.path.join(sockdir, "operator.sock")
            # Copy only the Python package into a disposable, non-root-readable staging tree.
            source = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agency")
            staged = os.path.join(folder, "code")
            os.mkdir(staged, 0o755)
            shutil.copytree(source, os.path.join(staged, "agency"),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for root, dirs, files in os.walk(staged):
                os.chmod(root, 0o755)
                for name in dirs:
                    os.chmod(os.path.join(root, name), 0o755)
                for name in files:
                    os.chmod(os.path.join(root, name), 0o644)
            request = json.dumps({"action": "approve", "approval_id": "test",
                                  "operator_secret_hex": "00"*32}).encode() + b"\n"
            def launch():
                proc = subprocess.Popen(
                    [sys.executable, "-c", CHILD, path, lock, freeze],
                    preexec_fn=lambda: (os.setgroups([]), os.setgid(identity.pw_gid),
                                       os.setuid(identity.pw_uid)),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=staged, env={**os.environ, "PYTHONPATH": staged},
                )
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if os.path.exists(path):
                        return proc
                    if proc.poll() is not None:
                        raise AssertionError("Staging listener exited: " + proc.stderr.read().decode())
                    time.sleep(0.05)
                proc.terminate()
                proc.wait(timeout=5)
                raise AssertionError("Staging listener not ready")
            def send():
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(3)
                    client.connect(path)
                    client.sendall(request)
                    return json.loads(client.recv(1024))["status"]
            def stop(proc):
                proc.terminate()
                try:
                    proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
            proc = None
            try:
                proc = launch()
                self.assertEqual(send(), "accepted")
                stop(proc)
                proc = None
                fd = os.open(freeze, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                self.assertEqual(stat.S_IMODE(os.stat(freeze).st_mode), 0o600)
                proc = launch()
                self.assertEqual(send(), "denied")
                stop(proc)
                proc = None
                proc = launch()
                self.assertEqual(send(), "denied")
                stop(proc)
                proc = None
                os.unlink(freeze)
                proc = launch()
                self.assertEqual(send(), "accepted")
            finally:
                if proc is not None:
                    stop(proc)


if __name__ == "__main__":
    unittest.main()
