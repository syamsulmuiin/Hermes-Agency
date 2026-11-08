"""Staging VM topology checks."""
import unittest
from agency.staging_runtime_topology import validate_topology


BASE = {"vm_id": "staging-001", "pid1": "systemd",
        "rootfs": "/staging/root", "journal": "/staging/state/owned.sqlite",
        "socket": "/staging/run/broker.sock",
        "admission_lock": "/staging/run/admission.lock",
        "freeze": "/staging/run/admission.freeze",
        "trusted_user": "staging_trusted", "worker_user": "staging_worker"}


class TopologyTests(unittest.TestCase):
    def test_valid_topology_never_authorizes(self):
        result = validate_topology(dict(BASE))
        self.assertTrue(result["topology_well_formed"])
        self.assertFalse(result["execute_authorized"])
        self.assertFalse(result["independent_vm_attested"])

    def test_missing_field_denied(self):
        data = dict(BASE)
        data.pop("journal")
        with self.assertRaises(PermissionError):
            validate_topology(data)

    def test_path_traversal_denied(self):
        data = dict(BASE, socket="/staging/../run/broker.sock")
        with self.assertRaises(PermissionError):
            validate_topology(data)

    def test_identity_alias_denied(self):
        data = dict(BASE, worker_user=BASE["trusted_user"])
        with self.assertRaises(PermissionError):
            validate_topology(data)


if __name__ == "__main__":
    unittest.main()
