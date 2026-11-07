"""Operator sidecar privilege separation tests; no host mutation."""
import types
import unittest
from unittest.mock import patch

from agency.operator_service import (
    load_private_secret, verify_private_broker_group, main,
)
from agency.operator_control import load_operator_verifier
from agency.operator_provision import provision_operator_verifier


class OperatorSidecarTests(unittest.TestCase):
    def test_root_cannot_start_sidecar(self):
        args = [
            "--state-dir", "/state", "--database", "/state/db",
            "--key-dir", "/state/keys", "--secret-file", "/state/secret",
            "--operator-socket", "/operator/sock",
            "--operator-verifier", "/state/verifier",
            "--broker-key", "/broker/key",
            "--broker-socket", "/broker/socket",
            "--worker-user", "hermes-worker",
        ]
        with patch("agency.operator_service.os.geteuid", return_value=0):
            with self.assertRaises(SystemExit) as result:
                main(args)
        self.assertEqual(result.exception.code, 2)

    def test_relative_path_denied_before_state_access(self):
        args = [
            "--state-dir", "relative", "--database", "/state/db",
            "--key-dir", "/state/keys", "--secret-file", "/state/secret",
            "--operator-socket", "/operator/sock",
            "--operator-verifier", "/state/verifier",
            "--broker-key", "/broker/key",
            "--broker-socket", "/broker/socket",
            "--worker-user", "hermes-worker",
        ]
        with patch("agency.operator_service.os.geteuid", return_value=2001):
            with patch("agency.operator_service.verify_private_state") as verify:
                with self.assertRaises(SystemExit) as result:
                    main(args)
                verify.assert_not_called()
        self.assertEqual(result.exception.code, 2)

    def test_worker_in_signing_key_group_denied(self):
        worker = types.SimpleNamespace(pw_uid=2002, pw_gid=3002, pw_name="worker")
        with (patch("agency.operator_service.os.geteuid", return_value=2001),
              patch("agency.operator_service.os.getegid", return_value=3001),
              patch("agency.operator_service.pwd.getpwnam", return_value=worker),
              patch("agency.operator_service.os.getgrouplist",
                    return_value=[3001, 3002]),
              patch("agency.operator_service._trusted_key")):
            with self.assertRaises(PermissionError):
                verify_private_broker_group("/broker/key", "worker")

    def test_worker_outside_private_key_group_allowed(self):
        worker = types.SimpleNamespace(pw_uid=2002, pw_gid=3002, pw_name="worker")
        with (patch("agency.operator_service.os.geteuid", return_value=2001),
              patch("agency.operator_service.os.getegid", return_value=3001),
              patch("agency.operator_service.pwd.getpwnam", return_value=worker),
              patch("agency.operator_service.os.getgrouplist",
                    return_value=[3002]),
              patch("agency.operator_service._trusted_key") as key):
            self.assertTrue(verify_private_broker_group("/broker/key", "worker"))
            key.assert_called_once_with("/broker/key")

    def test_worker_same_uid_denied(self):
        worker = types.SimpleNamespace(pw_uid=2001, pw_gid=3002, pw_name="worker")
        with (patch("agency.operator_service.os.geteuid", return_value=2001),
              patch("agency.operator_service.pwd.getpwnam", return_value=worker)):
            with self.assertRaises(PermissionError):
                verify_private_broker_group("/broker/key", "worker")

    def test_private_secret_never_read_as_root(self):
        with patch("agency.operator_service.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                load_private_secret("/state/secret")

    def test_operator_verifier_never_loaded_as_root(self):
        with patch("agency.operator_control.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                load_operator_verifier("/private/operator.json")

    def test_operator_verifier_provisioning_refuses_root(self):
        with patch("agency.operator_provision.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                provision_operator_verifier("/private/operator.json", "operator",
                                            "ff" * 32)


if __name__ == "__main__":
    unittest.main()
