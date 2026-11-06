"""Broker boundary integration tests: Unix peer, framing, replay and audit."""
import json
import os
import socket
import sqlite3
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.systemd_broker import handle_connection, provision_approval, verify_private_ledger, execute_approved as original_execute_approved


class BrokerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "ledger.sqlite")
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE approvals (id TEXT PRIMARY KEY, job TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY, approval_id TEXT, job TEXT, status TEXT, timestamp INTEGER)")
            db.execute("INSERT INTO approvals(id,job) VALUES (?,?)", ("x"*32, "noop"))
        self.guard = patch("agency.systemd_broker.verify_private_ledger")
        self.guard.start()

    def tearDown(self):
        self.guard.stop()
        self.tmp.cleanup()

    def send(self, payload, trusted_uid=None):
        a, b = socket.socketpair(socket.AF_UNIX)
        result = {}
        def server():
            try:
                with a:
                    result["value"] = handle_connection(a, os.getuid() if trusted_uid is None else trusted_uid, self.path)
            except Exception as exc:
                result["error"] = exc
        with patch("agency.systemd_broker.run_systemd_job", return_value={"job":"noop","exit_code":0}):
            # The default execute_approved captures its executor at definition time.
            with patch("agency.systemd_broker.execute_approved", side_effect=self.fake_execute):
                thread = threading.Thread(target=server)
                thread.start()
                with b:
                    try:
                        b.sendall(payload)
                        b.shutdown(socket.SHUT_WR)
                    except BrokenPipeError:
                        # Expected if peer identity is rejected before reading.
                        pass
                    try:
                        result["reply"] = b.recv(2048)
                    except OSError:
                        pass
                thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        return result

    def fake_execute(self, path, token, job):
        return original_execute_approved(path, token, job, executor=lambda name: {"job":name,"exit_code":0})

    def test_socket_success_and_replay_denial(self):
        payload = (json.dumps({"job":"noop","approval_id":"x"*32})+"\n").encode()
        first = self.send(payload)
        self.assertNotIn("error", first, repr(first.get("error")))
        self.assertEqual(first["value"]["exit_code"], 0)
        self.assertIn(b'"exit_code": 0', first["reply"])
        second = self.send(payload)
        self.assertIsInstance(second.get("error"), PermissionError)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 2)

    def test_wrong_uid_denied(self):
        result = self.send(b'{"job":"noop","approval_id":"'+b'x'*32+b'"}\n', trusted_uid=os.getuid()+1)
        self.assertIsInstance(result.get("error"), PermissionError)

    def test_extra_fields_denied(self):
        payload = (json.dumps({"job":"noop","approval_id":"x"*32,"command":"/bin/sh"})+"\n").encode()
        self.assertIsInstance(self.send(payload).get("error"), PermissionError)

    def test_no_newline_denied(self):
        self.assertIsInstance(self.send(b'{}').get("error"), PermissionError)

    def test_root_only_issuance(self):
        with patch("agency.systemd_broker.os.geteuid", return_value=995):
            with self.assertRaises(PermissionError):
                provision_approval(self.path, "z"*32, "noop")

    def test_invalid_issuance_job(self):
        with patch("agency.systemd_broker.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                provision_approval(self.path, "z"*32, "/bin/sh")

    def test_ledger_rejects_unprivileged_owner(self):
        self.guard.stop()
        try:
            with self.assertRaises(PermissionError):
                verify_private_ledger(self.path)
        finally:
            self.guard.start()


if __name__ == "__main__":
    unittest.main()
