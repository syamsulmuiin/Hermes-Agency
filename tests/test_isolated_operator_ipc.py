"""Regression checks for isolated operator IPC safety boundaries."""
import unittest
from unittest.mock import patch
from agency.isolated_operator_ipc import request_operator


class IsolatedOperatorIPCTests(unittest.TestCase):
    @patch("agency.isolated_operator_ipc.os.geteuid", return_value=0)
    def test_refuses_production_socket(self, _uid):
        with self.assertRaises(PermissionError):
            request_operator("/run/hermes-operator/operator.sock", {"action": "approve"})

    @patch("agency.isolated_operator_ipc.os.geteuid", return_value=0)
    def test_refuses_broker_socket(self, _uid):
        with self.assertRaises(PermissionError):
            request_operator("/run/hermes-broker/broker.sock", {"action": "approve"})

    @patch("agency.isolated_operator_ipc.os.geteuid", return_value=1000)
    def test_refuses_nonroot(self, _uid):
        with self.assertRaises(PermissionError):
            request_operator("/run/hermes-staging/x/operator.sock", {"action": "approve"})

    @patch("agency.isolated_operator_ipc.os.geteuid", return_value=0)
    def test_refuses_nonobject_request(self, _uid):
        with self.assertRaises(TypeError):
            request_operator("/run/hermes-staging/x/operator.sock", "approve")


if __name__ == "__main__":
    unittest.main()
