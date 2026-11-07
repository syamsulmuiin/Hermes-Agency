"""Dependency-injected maintenance tests; no production host access."""
import contextlib
import unittest

from agency.production_cutover_controller import cutover, CutoverError
from agency.production_maintenance_adapter import (
    MaintenanceAuthorization, MaintenanceDenied, ProductionMaintenanceAdapter)

AUTH = MaintenanceAuthorization('approved-window', 'a' * 40, 'runtime-a', 1, 2)


class FakeBackend:
    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []
        self.frozen = False
        self.quarantined = False
        self.route = 'legacy'
        self.ledger = ('persistent-ledger', 19)
        self.ledger_writes = 0

    def hit(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise RuntimeError('injected ' + name)

    @contextlib.contextmanager
    def exclusive_drain(self):
        self.hit('exclusive_drain')
        yield

    def lock_identity(self):
        self.hit('lock_identity')
        return (1, 2)

    def runtime_evidence(self):
        self.hit('runtime_evidence')
        return ('a' * 40, 'runtime-a')

    def freeze(self):
        self.frozen = True
        self.hit('freeze')

    def freeze_verified(self):
        self.hit('freeze_verified')
        return self.frozen

    def quiesce(self):
        self.hit('quiesce')

    def stop_old(self):
        self.hit('stop_old')

    def replay_ledger_identity(self):
        self.hit('replay_ledger_identity')
        return self.ledger

    def bootstrap_existing_journal(self):
        self.hit('bootstrap_existing_journal')

    def start_new(self):
        self.hit('start_new')

    def route_new(self):
        self.route = 'fenced'
        self.hit('route_new')

    def route_verified(self, route):
        self.hit('route_verified')
        return self.route == route

    def replay_denied(self):
        self.hit('replay_denied')
        return True

    def health(self):
        self.hit('health')

    def rollback_route_and_service(self):
        self.route = 'legacy'
        self.hit('rollback_route_and_service')

    def legacy_verified(self):
        self.hit('legacy_verified')
        return self.route == 'legacy'

    def unfreeze(self):
        self.hit('unfreeze')
        self.frozen = False

    def quarantine(self):
        self.quarantined = True
        self.frozen = True
        self.hit('quarantine')

    def quarantine_verified(self):
        self.hit('quarantine_verified')
        return self.quarantined and self.frozen


class MaintenanceTests(unittest.TestCase):
    def test_success(self):
        backend = FakeBackend()
        result = cutover(ProductionMaintenanceAdapter(backend, AUTH))
        self.assertEqual(result.status, 'PASS')
        self.assertEqual(backend.route, 'fenced')
        self.assertFalse(backend.frozen)
        self.assertEqual(backend.ledger_writes, 0)

    def test_failure_injection_every_phase(self):
        phases = ('runtime_evidence', 'freeze', 'quiesce', 'stop_old',
                  'bootstrap_existing_journal', 'start_new', 'route_new',
                  'replay_denied', 'health', 'unfreeze')
        for phase in phases:
            with self.subTest(phase=phase):
                backend = FakeBackend(phase)
                with self.assertRaises(CutoverError):
                    cutover(ProductionMaintenanceAdapter(backend, AUTH))
                self.assertEqual(backend.ledger_writes, 0)
                self.assertEqual(backend.ledger, ('persistent-ledger', 19))
                self.assertEqual(backend.route, 'legacy' if phase != 'unfreeze' else 'fenced')

    def test_failed_rollback_durable_quarantine(self):
        backend = FakeBackend('rollback_route_and_service')
        original = backend.route_new
        def broken_route():
            original()
            raise RuntimeError('route failure')
        backend.route_new = broken_route
        with self.assertRaises(CutoverError):
            cutover(ProductionMaintenanceAdapter(backend, AUTH))
        self.assertTrue(backend.quarantined)
        self.assertTrue(backend.frozen)
        self.assertNotIn('unfreeze', backend.calls)

    def test_stale_runtime_denied(self):
        backend = FakeBackend()
        backend.runtime_evidence = lambda: ('b' * 40, 'runtime-a')
        with self.assertRaises(CutoverError):
            cutover(ProductionMaintenanceAdapter(backend, AUTH))
        self.assertNotIn('stop_old', backend.calls)

    def test_lock_inode_change_denied(self):
        backend = FakeBackend()
        backend.lock_identity = lambda: (1, 3)
        with self.assertRaises(MaintenanceDenied):
            cutover(ProductionMaintenanceAdapter(backend, AUTH))
        self.assertNotIn('stop_old', backend.calls)

    def test_missing_approval_denied(self):
        with self.assertRaises(MaintenanceDenied):
            ProductionMaintenanceAdapter(FakeBackend(), None)

    def test_ledger_identity_change_quarantines(self):
        backend = FakeBackend()
        original = backend.bootstrap_existing_journal
        def tamper():
            original()
            backend.ledger = ('replaced', 20)
        backend.bootstrap_existing_journal = tamper
        with self.assertRaises(CutoverError):
            cutover(ProductionMaintenanceAdapter(backend, AUTH))
        self.assertTrue(backend.quarantined)
        self.assertNotIn('unfreeze', backend.calls)


if __name__ == '__main__':
    unittest.main()
