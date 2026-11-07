"""Opt-in operator lifecycle negative tests; never deploys a service."""
import unittest
from unittest.mock import patch

from agency.service_lifecycle import serve_forever
from agency.single_vps_service import main
from agency.operator_control import load_operator_verifier
from agency.operator_provision import provision_operator_verifier


def config(**overrides):
    data = {
        "socket_path": "/operator/operator.sock",
        "verifier_path": "/private/operator-verifier.json",
        "broker_key_path": "/broker/signing.key",
        "broker_socket_path": "/broker/broker.sock",
    }
    data.update(overrides)
    return data


class OperatorServiceOptionsTests(unittest.TestCase):
    def test_same_worker_and_operator_path_denied_before_key_access(self):
        with self.assertRaises(PermissionError):
            serve_forever(
                "/operator/operator.sock", "/state", "/db", "/keys",
                2000, frozenset({2001}), b"k" * 64,
                operator_config=config(),
            )

    def test_shared_worker_operator_directory_denied(self):
        with self.assertRaises(PermissionError):
            serve_forever(
                "/operator/worker.sock", "/state", "/db", "/keys",
                2000, frozenset({2001}), b"k" * 64,
                operator_config=config(),
            )

    def test_relative_operator_paths_denied(self):
        with self.assertRaises(PermissionError):
            serve_forever(
                "/worker/trusted.sock", "/state", "/db", "/keys",
                2000, frozenset({2001}), b"k" * 64,
                operator_config=config(verifier_path="relative.json"),
            )

    def test_incomplete_cli_opt_in_refused_before_secret_read(self):
        args = [
            "--forever", "--socket", "/worker/stage.sock",
            "--state-dir", "/state", "--database", "/state/db",
            "--key-dir", "/state/keys", "--client-gid", "3000",
            "--allow-uid", "3001", "--secret-file", "/secret",
            "--operator-socket", "/operator/operator.sock",
        ]
        with self.assertRaises(SystemExit) as result:
            main(args)
        self.assertEqual(result.exception.code, 2)

    def test_operator_verifier_never_loaded_as_root(self):
        with patch("agency.operator_control.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                load_operator_verifier("/private/operator.json")

    def test_operator_verifier_provisioning_refuses_root(self):
        with patch("agency.operator_provision.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                provision_operator_verifier(
                    "/private/operator.json", "operator", "ff" * 32,
                )


if __name__ == "__main__":
    unittest.main()
