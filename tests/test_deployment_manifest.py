import copy
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, Mock
from agency.deployment_manifest import validate, resolve, load, _trusted_systemctl

BASE = {
    "schema": "hermes-deployment-v1",
    "paths": {
        "snapshot": "/opt/hermes-fenced-test",
        "admission_lock": "/run/test/admission.lock",
        "freeze_marker": "/run/test/freeze",
        "operator_socket": "/run/test/operator.sock",
    },
    "units": {
        "agency": "agency.service", "broker": "broker.service",
        "sidecar": "sidecar.service", "candidate_broker": "candidate.service",
        "candidate_recovery": "recovery.service",
    },
    "identities": {
        "trusted_user": "trusted", "trusted_group": "agents",
        "worker_user": "worker",
    },
}


class DeploymentManifestTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(copy.deepcopy(BASE))["schema"], "hermes-deployment-v1")

    def test_traversal_rejected(self):
        data = copy.deepcopy(BASE)
        data["paths"]["snapshot"] = "/opt/../root"
        with self.assertRaises(ValueError):
            validate(data)

    def test_extra_field_rejected(self):
        data = copy.deepcopy(BASE)
        data["execute"] = True
        with self.assertRaises(ValueError):
            validate(data)

    def test_invalid_unit_rejected(self):
        data = copy.deepcopy(BASE)
        data["units"]["broker"] = "broker;restart.service"
        with self.assertRaises(ValueError):
            validate(data)

    def test_manifest_file_symlink_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.json"
            source.write_text(json.dumps(BASE))
            link = Path(temp) / "link.json"
            link.symlink_to(source)
            with patch("agency.deployment_manifest._trusted_chain"):
                with self.assertRaises(OSError):
                    load(str(link))

    def test_manifest_file_group_writable_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "manifest.json"
            source.write_text(json.dumps(BASE))
            source.chmod(0o664)
            with patch("agency.deployment_manifest._trusted_chain"):
                with self.assertRaises(PermissionError):
                    load(str(source))

    def test_manifest_file_inode_pinned(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "manifest.json"
            source.write_text(json.dumps(BASE))
            source.chmod(0o600)
            with patch("agency.deployment_manifest._trusted_chain"):
                if os.geteuid() == 0:
                    self.assertEqual(load(str(source))["schema"], "hermes-deployment-v1")
                else:
                    with self.assertRaises(PermissionError):
                        load(str(source))

    def test_untrusted_systemctl_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "systemctl"
            executable.write_text("#!/bin/sh\\n")
            executable.chmod(0o777)
            with self.assertRaises(PermissionError):
                _trusted_systemctl(str(executable))

    @patch("agency.deployment_manifest.grp.getgrnam")
    @patch("agency.deployment_manifest.pwd.getpwnam")
    def test_resolver_is_non_authorizing(self, user, group):
        user.return_value = Mock(pw_uid=1001)
        group.return_value = Mock(gr_gid=1002)
        result = resolve(copy.deepcopy(BASE),
                         which=lambda _: "/usr/bin/systemctl",
                         run=lambda *a, **kw: Mock(returncode=0))
        self.assertFalse(result["cutover_authorized"])
        self.assertFalse(result["sandbox_authorized"])
        self.assertFalse(result["runtime_behavior_attested"])
        self.assertEqual(result["uids"]["trusted_user"], 1001)


if __name__ == "__main__":
    unittest.main()
