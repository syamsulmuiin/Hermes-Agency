"""Fail-closed maintenance adapter contract; no production CLI or default backend.

An operator-reviewed backend must implement every operation. The adapter is
inert until an explicit authorization object and independent backend are passed.
Staging adapters must never be substituted for this interface.
"""
from contextlib import contextmanager
from dataclasses import dataclass


class MaintenanceDenied(RuntimeError):
    """Missing, stale, or unverified maintenance evidence."""


@dataclass(frozen=True)
class MaintenanceAuthorization:
    window_id: str
    approved_commit: str
    runtime_identity: str
    lock_device: int
    lock_inode: int

    def validate(self):
        if (not self.window_id or len(self.approved_commit) != 40
                or any(c not in '0123456789abcdef' for c in self.approved_commit)
                or not self.runtime_identity or self.lock_device <= 0
                or self.lock_inode <= 0):
            raise MaintenanceDenied('Incomplete maintenance authorization')


class ProductionMaintenanceAdapter:
    """Adapter for existing cutover() with all host operations injected.

    Backend methods: exclusive_drain, runtime_evidence, lock_identity,
    freeze, freeze_verified, quiesce, stop_old, bootstrap_existing_journal,
    start_new, route_new, route_verified, replay_denied, health,
    rollback_route_and_service, legacy_verified, unfreeze, quarantine,
    quarantine_verified, replay_ledger_identity.

    Backend owns durable host implementation. No shell commands, paths, or
    production service names are inferred or hardcoded here.
    """

    def __init__(self, backend, authorization):
        if not isinstance(authorization, MaintenanceAuthorization):
            raise MaintenanceDenied('Explicit authorization required')
        authorization.validate()
        self.backend = backend
        self.authorization = authorization
        self._drained = False
        self._frozen = False
        self._ledger = None
        self._phase = 'created'
        self._healthy = False

    def _require_drain(self):
        if not self._drained:
            raise MaintenanceDenied('Exclusive drain not held')
        if tuple(self.backend.lock_identity()) != (
                self.authorization.lock_device, self.authorization.lock_inode):
            raise MaintenanceDenied('Admission lock inode changed')

    def _require_frozen(self):
        self._require_drain()
        if not self._frozen or self.backend.freeze_verified() is not True:
            raise MaintenanceDenied('Durable freeze not verified')

    def _check_ledger(self):
        if self._ledger is None or self.backend.replay_ledger_identity() != self._ledger:
            raise MaintenanceDenied('Persistent replay ledger identity changed')

    @contextmanager
    def admission_drain(self):
        if self._drained:
            raise MaintenanceDenied('Nested maintenance drain')
        with self.backend.exclusive_drain():
            self._drained = True
            try:
                self._require_drain()
                yield
            finally:
                self._drained = False

    def attest(self):
        self._require_drain()
        evidence = self.backend.runtime_evidence()
        expected = (self.authorization.approved_commit,
                    self.authorization.runtime_identity)
        if not isinstance(evidence, tuple) or evidence != expected:
            raise MaintenanceDenied('Runtime identity mismatch')
        self._phase = 'attested'

    def freeze(self):
        self._require_drain()
        self.backend.freeze()
        self._frozen = True
        self._require_frozen()
        self._phase = 'frozen'

    def quiesce(self):
        self._require_frozen()
        self.backend.quiesce()
        self._phase = 'quiesced'

    def stop_old(self):
        self._require_frozen()
        self.backend.stop_old()
        self._phase = 'old_stopped'

    def bootstrap(self):
        self._require_frozen()
        self._ledger = self.backend.replay_ledger_identity()
        if not self._ledger:
            raise MaintenanceDenied('Replay ledger not attested')
        self.backend.bootstrap_existing_journal()
        self._check_ledger()
        self._phase = 'journal_ready'

    def start_new(self):
        self._require_frozen()
        self._check_ledger()
        self.backend.start_new()
        self._phase = 'new_started'

    def route_new(self):
        self._require_frozen()
        self.backend.route_new()
        if self.backend.route_verified('fenced') is not True:
            raise MaintenanceDenied('Candidate route not verified')
        self._phase = 'new_routed'

    def replay_probe(self):
        self._require_frozen()
        self._check_ledger()
        if self.backend.replay_denied() is not True:
            raise MaintenanceDenied('Replay protection not proven')
        self._check_ledger()
        self._phase = 'replay_denied'

    def health(self):
        self._require_drain()
        self.backend.health()
        expected = 'legacy' if self._phase == 'rolled_back' else 'fenced'
        if self.backend.route_verified(expected) is not True:
            raise MaintenanceDenied('Health route mismatch')
        if self._ledger is not None:
            self._check_ledger()
        self._healthy = True

    def rollback(self):
        self._require_drain()
        self._healthy = False
        self.backend.rollback_route_and_service()
        if self.backend.legacy_verified() is not True:
            raise MaintenanceDenied('Legacy rollback not verified')
        if self._ledger is not None:
            self._check_ledger()
        self._phase = 'rolled_back'

    def unfreeze(self):
        self._require_drain()
        if not self._healthy or self._phase not in ('rolled_back', 'replay_denied'):
            raise MaintenanceDenied('Admission reopening is not authorized')
        if self._phase == 'replay_denied':
            self.health()
        else:
            if self.backend.legacy_verified() is not True:
                raise MaintenanceDenied('Rollback not verified')
        self.backend.unfreeze()
        if self.backend.freeze_verified() is not False:
            raise MaintenanceDenied('Admission unfreeze not verified')
        self._frozen = False
        self._phase = 'unfrozen'

    def quarantine(self):
        self.backend.quarantine()
        if self.backend.quarantine_verified() is not True:
            raise MaintenanceDenied('Durable quarantine not verified')
        self._frozen = True
        self._phase = 'quarantined'
