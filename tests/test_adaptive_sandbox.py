import unittest
from unittest.mock import patch

from agency.adaptive_sandbox import ORDER, choose_backend, inventory, require_adaptive_executor


class AdaptiveSandboxTests(unittest.TestCase):
    def test_inventory_does_not_authorize(self):
        with patch("agency.adaptive_sandbox.discover_backends", return_value={
            "platform": "linux",
            "candidates": {"docker": {"cli_installed": True},
                           "podman": {"cli_installed": True}},
        }), patch("agency.adaptive_sandbox.assess_linux_isolation", return_value={
            "kernel_prerequisites_present": True,
        }):
            result = inventory()
        self.assertIsNone(result["selected"])
        self.assertFalse(result["agent_tools_enabled"])
        self.assertFalse(any(item["validated"] for item in result["candidates"].values()))

    def test_incomplete_evidence_denied(self):
        with self.assertRaises(PermissionError):
            choose_backend({"validated": {"docker": True}, "policy_approved": {}})

    def test_non_boolean_evidence_denied(self):
        values = {name: False for name in ORDER}
        values["docker"] = 1
        with self.assertRaises(PermissionError):
            choose_backend({"validated": values, "policy_approved": {name: True for name in ORDER}})

    def test_planning_never_enables_tools(self):
        values = {name: True for name in ORDER}
        result = choose_backend({"validated": values, "policy_approved": values})
        self.assertEqual(result["candidate"], ORDER[0])
        self.assertFalse(result["agent_tools_enabled"])

    def test_no_backend_is_denied(self):
        values = {name: False for name in ORDER}
        result = choose_backend({"validated": values, "policy_approved": values})
        self.assertIsNone(result["candidate"])
        with self.assertRaises(PermissionError):
            require_adaptive_executor()


if __name__ == "__main__":
    unittest.main()
