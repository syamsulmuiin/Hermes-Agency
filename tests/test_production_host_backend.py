"""Isolated host backend failure injection and non-authorizing readiness tests."""
import fcntl
import os
from pathlib import Path
import tempfile
import unittest

from agency.production_host_backend import IsolatedHostBackend
from agency.production_maintenance_adapter import MaintenanceDenied
from agency.production_maintenance_readiness import evaluate, REQUIRED


class Ops:
    def __init__(self):
        self.participates = True
        self.fail = None
        self.calls = []

    def admission_participation_verified(self):
        self.calls.append('admission')
        return self.participates

    def __getattr__(self, name):
        def operation(*args):
            self.calls.append(name)
            if name == self.fail:
                raise RuntimeError(name)
            if name.endswith('_verified') or name == 'replay_denied':
                return True
            if name == 'runtime_evidence':
                return ('a' * 40, 'runtime-a')
            if name == 'replay_ledger_identity':
                return ('durable-ledger', 11)
        return operation


class IsolatedHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.lock = root / 'admission.lock'
        self.lock.touch(mode=0o640)
        os.chmod(self.lock, 0o640)
        self.freeze = root / 'admission.freeze'
        self.ops = Ops()
        self.host = IsolatedHostBackend(self.lock, self.freeze, self.ops)

    def test_drain_retains_inode(self):
        with self.host.exclusive_drain():
            inode = self.host.lock_identity()
            self.assertEqual(inode, (self.lock.stat().st_dev, self.lock.stat().st_ino))
        with self.assertRaises(MaintenanceDenied):
            self.host.lock_identity()

    def test_missing_participation_denied(self):
        self.ops.participates = False
        with self.assertRaises(MaintenanceDenied):
            with self.host.exclusive_drain():
                self.fail('must not acquire unverified drain')

    def test_inode_replacement_denied(self):
        with self.host.exclusive_drain():
            self.lock.unlink()
            self.lock.touch(mode=0o640)
            os.chmod(self.lock, 0o640)
            with self.assertRaises(MaintenanceDenied):
                self.host.lock_identity()

    def test_external_lock_denied(self):
        with self.lock.open('rb') as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                with self.host.exclusive_drain():
                    pass

    def test_deny_all_default(self):
        host = IsolatedHostBackend(self.lock, self.freeze)
        with self.assertRaises(MaintenanceDenied):
            with host.exclusive_drain():
                pass

    def test_failure_injection_no_implicit_retry(self):
        self.ops.fail = 'stop_old'
        with self.assertRaises(RuntimeError):
            self.host.stop_old()
        self.assertEqual(self.ops.calls.count('stop_old'), 1)

    def test_readiness_requires_independent_live_attestation(self):
        all_true = {key: True for key in REQUIRED}
        self.assertEqual(evaluate(all_true).status, 'NO_GO')
        self.assertEqual(evaluate(all_true, production_attested=True).status, 'GO')
        for key in REQUIRED:
            with self.subTest(key=key):
                evidence = dict(all_true)
                evidence[key] = False
                self.assertEqual(evaluate(evidence, production_attested=True).status, 'NO_GO')


if __name__ == '__main__':
    unittest.main()
