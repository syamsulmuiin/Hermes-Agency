"""Integration tests for portable backend and existing cutover rollback."""
import unittest

from agency.portable_production_backend import (
    HostOperations, OPERATIONS, PortableProductionBackend)
from agency.production_maintenance_adapter import (
    MaintenanceDenied, ProductionMaintenanceAdapter)
from agency.production_cutover_controller import cutover, CutoverError
from tests.test_production_maintenance_adapter import FakeBackend, AUTH


MANIFEST = {
    "schema": "hermes-deployment-v1",
    "paths": {
        "snapshot": "/srv/hermes/candidate",
        "admission_lock": "/run/hermes/admission.lock",
        "freeze_marker": "/run/hermes/admission.freeze",
        "operator_socket": "/run/hermes/operator.sock",
    },
    "units": {
        "agency": "agency.service", "broker": "broker.service",
        "sidecar": "sidecar.service",
        "candidate_broker": "candidate.service",
        "candidate_recovery": "recovery.service",
    },
    "identities": {
        "trusted_user": "trusted", "trusted_group": "agents",
        "worker_user": "worker",
    },
}


def resolver(manifest):
    return {"identity_resolved": True, "cutover_authorized": False,
            "sandbox_authorized": False, "paths": manifest["paths"],
            "units": manifest["units"]}


def bind(fake):
    return HostOperations(**{
        name: (lambda resolved, *args, name=name: getattr(fake, name)(*args))
        for name in OPERATIONS
    })


class PortableBackendTests(unittest.TestCase):
    def test_success_uses_existing_controller(self):
        fake = FakeBackend()
        backend = PortableProductionBackend(MANIFEST, bind(fake), resolver=resolver)
        result = cutover(ProductionMaintenanceAdapter(backend, AUTH))
        self.assertEqual(result.status, "PASS")
        self.assertEqual(fake.route, "fenced")
        self.assertEqual(fake.ledger, ("persistent-ledger", 19))

    def test_failed_rollback_quarantines_without_ledger_reset(self):
        fake = FakeBackend("rollback_route_and_service")
        original = fake.route_new

        def broken():
            original()
            raise RuntimeError("route failure")

        fake.route_new = broken
        backend = PortableProductionBackend(MANIFEST, bind(fake), resolver=resolver)
        with self.assertRaises(CutoverError):
            cutover(ProductionMaintenanceAdapter(backend, AUTH))
        self.assertTrue(fake.quarantined)
        self.assertTrue(fake.frozen)
        self.assertNotIn("unfreeze", fake.calls)
        self.assertEqual(fake.ledger, ("persistent-ledger", 19))

    def test_operation_outside_drain_denied(self):
        backend = PortableProductionBackend(MANIFEST, bind(FakeBackend()), resolver=resolver)
        with self.assertRaises(MaintenanceDenied):
            backend.stop_old()

    def test_incomplete_bindings_denied(self):
        with self.assertRaises(MaintenanceDenied):
            PortableProductionBackend(MANIFEST, object(), resolver=resolver)

    def test_untrusted_resolver_denied(self):
        def unsafe(manifest):
            result = resolver(manifest)
            result["cutover_authorized"] = True
            return result
        with self.assertRaises(MaintenanceDenied):
            PortableProductionBackend(MANIFEST, bind(FakeBackend()), resolver=unsafe)


if __name__ == "__main__":
    unittest.main()
