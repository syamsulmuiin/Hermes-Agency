"""Portable production maintenance backend using existing operator integrations.

This module provides no default host operations or execution entrypoint.
A reviewed integration must supply every callable and a validated deployment
manifest. No staging adapter or fake fallback is accepted.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os

from .deployment_manifest import validate, resolve
from .production_maintenance_adapter import MaintenanceDenied


OPERATIONS = (
    "exclusive_drain", "runtime_evidence", "lock_identity", "freeze",
    "freeze_verified", "quiesce", "stop_old", "bootstrap_existing_journal",
    "start_new", "route_new", "route_verified", "replay_denied", "health",
    "rollback_route_and_service", "legacy_verified", "unfreeze",
    "quarantine", "quarantine_verified", "replay_ledger_identity",
)


@dataclass(frozen=True)
class HostOperations:
    """Explicit host bindings. No implicit shell/systemd implementation."""
    exclusive_drain: object
    runtime_evidence: object
    lock_identity: object
    freeze: object
    freeze_verified: object
    quiesce: object
    stop_old: object
    bootstrap_existing_journal: object
    start_new: object
    route_new: object
    route_verified: object
    replay_denied: object
    health: object
    rollback_route_and_service: object
    legacy_verified: object
    unfreeze: object
    quarantine: object
    quarantine_verified: object
    replay_ledger_identity: object


class PortableProductionBackend:
    """Fail-closed bridge from existing host operations to maintenance adapter."""

    def __init__(self, manifest, operations, *, resolver=resolve):
        validate(manifest)
        if not isinstance(operations, HostOperations):
            raise MaintenanceDenied("Reviewed host operation bindings required")
        if any(not callable(getattr(operations, name)) for name in OPERATIONS):
            raise MaintenanceDenied("Incomplete production operation bindings")
        resolved = resolver(manifest)
        if (resolved.get("identity_resolved") is not True
                or resolved.get("cutover_authorized") is not False
                or resolved.get("sandbox_authorized") is not False
                or resolved.get("paths") != manifest["paths"]
                or resolved.get("units") != manifest["units"]):
            raise MaintenanceDenied("Invalid portable runtime resolution")
        self.manifest = manifest
        self.resolved = resolved
        self._ops = operations
        self._drained = False

    def _invoke(self, name, *args):
        if not self._drained:
            raise MaintenanceDenied("Exclusive maintenance drain required")
        return getattr(self._ops, name)(self.resolved, *args)

    @contextmanager
    def exclusive_drain(self):
        if self._drained:
            raise MaintenanceDenied("Nested exclusive drain")
        with self._ops.exclusive_drain(self.resolved):
            self._drained = True
            try:
                yield
            finally:
                self._drained = False

    def lock_identity(self):
        return self._invoke("lock_identity")

    def runtime_evidence(self):
        return self._invoke("runtime_evidence")

    def freeze(self):
        return self._invoke("freeze")

    def freeze_verified(self):
        return self._invoke("freeze_verified")

    def quiesce(self):
        return self._invoke("quiesce")

    def stop_old(self):
        return self._invoke("stop_old")

    def bootstrap_existing_journal(self):
        return self._invoke("bootstrap_existing_journal")

    def start_new(self):
        return self._invoke("start_new")

    def route_new(self):
        return self._invoke("route_new")

    def route_verified(self, route):
        return self._invoke("route_verified", route)

    def replay_denied(self):
        return self._invoke("replay_denied")

    def health(self):
        return self._invoke("health")

    def rollback_route_and_service(self):
        return self._invoke("rollback_route_and_service")

    def legacy_verified(self):
        return self._invoke("legacy_verified")

    def unfreeze(self):
        return self._invoke("unfreeze")

    def quarantine(self):
        return self._invoke("quarantine")

    def quarantine_verified(self):
        return self._invoke("quarantine_verified")

    def replay_ledger_identity(self):
        return self._invoke("replay_ledger_identity")
