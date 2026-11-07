"""Real trusted approval -> signed grant -> Unix socket -> broker test.

Uses a fake fixed-job executor in unit tests. Production remains disabled.
"""
import json
import os
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.broker_grants import issue_broker_grant
from agency.systemd_broker import handle_signed_connection


class TrustedBrokerSocketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = [100.0]
        self.trusted_path = str(Path(self.tmp.name) / "trusted.sqlite")
        self.ledger = str(Path(self.tmp.name) / "broker.sqlite")
        self.store = SecureAgencyStore(self.trusted_path, clock=lambda: self.clock[0])
        self.auth = TrustedApprovalService(self.store, b"s"*32, clock=lambda: self.clock[0])
        self.task = self.store.create_task("Broker integration", "developer")
        self.lease = self.store.claim(self.task, "worker", ttl=60)
        self.worker = self.auth.issue_credential("worker", "worker")
        self.approval = self.store.request_approval(self.task, "execute_shell",
                                                    {"job":"noop"}, "developer")
        self.auth.decide(self.approval, self.auth.issue_credential("reviewer","approver"), True)
        self.key = b"k"*32
        self.grant = issue_broker_grant(self.auth, self.approval, self.task,
                                       "noop", self.worker, self.lease, self.key)
        sqlite3.connect(self.ledger).close()
        self.guard = patch("agency.systemd_broker.verify_private_ledger")
        self.guard.start()

    def tearDown(self):
        self.guard.stop()
        self.store.close()
        self.tmp.cleanup()

    def send(self, grant, uid=None):
        a,b = socket.socketpair()
        result = {}
        def serve():
            try:
                with a:
                    result["value"] = handle_signed_connection(
                        a, os.getuid() if uid is None else uid,
                        self.ledger, self.trusted_path, self.key,
                        executor=lambda job: {"job":job,"exit_code":0}, now=self.clock[0])
            except Exception as exc:
                result["error"] = exc
        thread = threading.Thread(target=serve)
        thread.start()
        with b:
            try:
                b.sendall((json.dumps({"grant":grant})+"\n").encode())
                b.shutdown(socket.SHUT_WR)
                result["reply"] = b.recv(4096)
            except (BrokenPipeError, ConnectionResetError):
                pass
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        return result

    def test_actual_approved_grant_socket_and_replay(self):
        first = self.send(self.grant)
        self.assertNotIn("error", first, str(first.get("error")))
        self.assertEqual(first["value"]["exit_code"], 0)
        self.assertIsInstance(self.send(self.grant).get("error"), PermissionError)

    def test_revoked_lease_denied(self):
        self.store.db.execute("DELETE FROM task_leases WHERE task_id=?", (self.task,))
        self.store.db.commit()
        self.assertIsInstance(self.send(self.grant).get("error"), PermissionError)

    def test_expired_lease_denied(self):
        self.clock[0] = 161
        self.assertIsInstance(self.send(self.grant).get("error"), PermissionError)

    def test_wrong_peer_uid_denied(self):
        self.assertIsInstance(self.send(self.grant, uid=os.getuid()+1).get("error"), PermissionError)

    def test_forged_job_denied(self):
        altered = {"claims":dict(self.grant["claims"]), "signature":self.grant["signature"]}
        altered["claims"]["job"] = "identity"
        self.assertIsInstance(self.send(altered).get("error"), PermissionError)


if __name__ == "__main__":
    unittest.main()
