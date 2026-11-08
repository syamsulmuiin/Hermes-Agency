import copy
import unittest
from unittest.mock import patch, Mock
from agency.deployment_manifest import validate, resolve

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
