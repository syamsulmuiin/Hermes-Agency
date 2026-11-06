import hashlib
import hmac
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.broker_grants import _canonical, verify_broker_grant
from agency.security import fingerprint
from agency.systemd_broker import execute_signed_grant


class SignedBrokerGrantTests(unittest.TestCase):
    def setUp(self):
        self.key = b"k" * 32
        self.claims = dict(v=1, aud="hermes-systemd-broker-v1", id="a"*64,
                           approval="approval", task="task", worker="Developer",
                           lease_generation=2, job="noop",
                           params_hash=fingerprint({"job":"noop"}),
                           iat=100, exp=120)
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "ledger.sqlite")
        sqlite3.connect(self.db).close()
        self.guard = patch("agency.systemd_broker.verify_private_ledger")
        self.guard.start()

    def tearDown(self):
        self.guard.stop()
        self.tmp.cleanup()

    def signed(self):
        return {"claims": dict(self.claims),
                "signature": hmac.new(self.key, _canonical(self.claims), hashlib.sha256).hexdigest()}

    def test_verified_and_consumed_once(self):
        envelope = self.signed()
        calls = []
        execute_signed_grant(self.db, envelope, self.key, now=110,
                             executor=lambda job: calls.append(job) or {"ok":True})
        with self.assertRaises(PermissionError):
            execute_signed_grant(self.db, envelope, self.key, now=110,
                                 executor=lambda job: calls.append(job))
        self.assertEqual(calls, ["noop"])
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT status FROM signed_grant_consumptions").fetchone(), ("completed",))

    def test_expired_rejected(self):
        with self.assertRaises(PermissionError):
            verify_broker_grant(self.signed(), self.key, now=121)

    def test_future_rejected(self):
        with self.assertRaises(PermissionError):
            verify_broker_grant(self.signed(), self.key, now=99)

    def test_tampered_worker_rejected(self):
        envelope = self.signed()
        envelope["claims"]["worker"] = "QA"
        with self.assertRaises(PermissionError):
            verify_broker_grant(envelope, self.key, now=110)

    def test_tampered_job_rejected(self):
        envelope = self.signed()
        envelope["claims"]["job"] = "identity"
        with self.assertRaises(PermissionError):
            verify_broker_grant(envelope, self.key, now=110)

    def test_wrong_key_rejected(self):
        with self.assertRaises(PermissionError):
            verify_broker_grant(self.signed(), b"z"*32, now=110)

    def test_failed_execution_cannot_replay(self):
        def fail(job):
            raise RuntimeError("failure")
        with self.assertRaises(RuntimeError):
            execute_signed_grant(self.db, self.signed(), self.key, now=110, executor=fail)
        with self.assertRaises(PermissionError):
            execute_signed_grant(self.db, self.signed(), self.key, now=110, executor=lambda job: None)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT status FROM signed_grant_consumptions").fetchone(), ("failed",))


if __name__ == "__main__":
    unittest.main()
