"""Fail-closed portable staging installer phase tests."""
import copy
import hashlib
import unittest
from unittest.mock import patch

from agency.portable_staging_installer import validate, render_units, execute, main
from tests.test_deployment_manifest import BASE


def fake_resolver(manifest):
    return {"identity_resolved": True, "runtime_behavior_attested": False,
            "sandbox_authorized": False, "cutover_authorized": False,
            "paths": dict(manifest["paths"]), "units": dict(manifest["units"]),
            "uids": {"trusted_user": 1001, "worker_user": 1002},
            "gids": {"trusted_group": 1003},
            "systemctl": "/usr/bin/systemctl"}


class StagingInstallerTests(unittest.TestCase):
    def test_validate_never_authorizes(self):
        result = validate(copy.deepcopy(BASE), resolver=fake_resolver,
                          snapshot_audit=lambda _: {"agency/__init__.py": "a" * 64})
        self.assertFalse(result["execute_authorized"])
        self.assertFalse(result["source_commit_attested"])
        self.assertFalse(result["isolated_pid1_attested"])
        self.assertFalse(result["recovery_attested"])

    def test_empty_snapshot_inventory_denied(self):
        with self.assertRaises(PermissionError):
            validate(copy.deepcopy(BASE), resolver=fake_resolver,
                     snapshot_audit=lambda _: {})

    def test_invalid_snapshot_digest_denied(self):
        with self.assertRaises(PermissionError):
            validate(copy.deepcopy(BASE), resolver=fake_resolver,
                     snapshot_audit=lambda _: {"file": "not-a-digest"})

    def test_resolver_authorization_injection_denied(self):
        def unsafe(manifest):
            value = fake_resolver(manifest)
            value["cutover_authorized"] = True
            return value
        with self.assertRaises(PermissionError):
            validate(copy.deepcopy(BASE), resolver=unsafe,
                     snapshot_audit=lambda _: {"file": "b" * 64})

    def test_unit_templates_use_manifest_and_are_inert(self):
        manifest = copy.deepcopy(BASE)
        manifest["paths"]["snapshot"] = "/srv/isolated/candidate"
        manifest["units"]["candidate_recovery"] = "isolated-recovery.service"
        result = render_units(manifest)
        self.assertIn("/srv/isolated/candidate", result["broker"])
        self.assertIn("isolated-recovery.service", result["broker"])
        for text in result.values():
            self.assertIn("RefuseManualStart=yes", text)
            self.assertNotIn("fenced_owned_recovery --execute", text)
            self.assertNotIn("fenced_broker_candidate --execute", text)
            self.assertNotIn("/var/lib/hermes-broker", text)

    def test_execute_unconditionally_denied(self):
        for attestation in (None, {}, {"isolated": True, "approved": True}):
            with self.subTest(attestation=attestation):
                with self.assertRaises(PermissionError):
                    execute(isolation_attestation=attestation)

    def test_execute_cli_does_not_load_manifest(self):
        self.assertEqual(main(["execute", "--manifest", "/does/not/exist"]), 2)


if __name__ == "__main__":
    unittest.main()
