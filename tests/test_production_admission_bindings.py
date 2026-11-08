"""Safe integration tests for real admission binding selection."""
import unittest

from agency.portable_production_backend import bind_existing_admission
from agency.production_admission_bindings import ProductionAdmissionBindings
from agency.production_maintenance_adapter import MaintenanceDenied
from tests.test_portable_production_backend import FakeBackend, bind


class AdmissionBindingTests(unittest.TestCase):
    def test_replaces_only_drain_and_identity(self):
        original = bind(FakeBackend())
        bound = bind_existing_admission(original)
        self.assertEqual(bound.exclusive_drain.__self__.__class__,
                         ProductionAdmissionBindings)
        self.assertIs(bound.exclusive_drain.__self__, bound.lock_identity.__self__)
        self.assertIs(bound.freeze, original.freeze)
        self.assertIs(bound.rollback_route_and_service,
                      original.rollback_route_and_service)

    def test_identity_without_drain_denied(self):
        binding = ProductionAdmissionBindings()
        with self.assertRaises(MaintenanceDenied):
            binding.lock_identity({"paths": {"admission_lock": "/missing"}})

    def test_missing_lock_does_not_create_file(self):
        binding = ProductionAdmissionBindings()
        with self.assertRaises(FileNotFoundError):
            with binding.exclusive_drain(
                    {"paths": {"admission_lock": "/run/hermes-no-such-lock-test"}}):
                self.fail("must not enter drain")

    def test_fake_binding_rejected(self):
        with self.assertRaises(MaintenanceDenied):
            bind_existing_admission(bind(FakeBackend()), admission=object())


if __name__ == "__main__":
    unittest.main()
