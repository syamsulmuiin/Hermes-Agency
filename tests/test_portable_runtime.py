import unittest
from unittest.mock import patch

from agency.portable_runtime import PortableAgentRuntime
from agency.orchestrator import WorkflowCoordinator


class PortableRuntimeTests(unittest.TestCase):
    def test_requires_coordinator(self):
        with self.assertRaises(TypeError):
            PortableAgentRuntime(object())

    def test_no_backend_does_not_disable_workflow(self):
        # Construct without initializing a database: capability reporting
        # must not depend on a working shell, Docker, or Bubblewrap.
        runtime = object.__new__(PortableAgentRuntime)
        runtime.coordinator = object.__new__(WorkflowCoordinator)
        report = {"backend": "disabled", "agent_tools_enabled": False}
        with patch("agency.portable_runtime.discover_backends", return_value=report):
            capabilities = runtime.capabilities()
        self.assertTrue(capabilities["workflow_available"])
        self.assertFalse(capabilities["tool_execution_available"])
        self.assertIs(capabilities["sandbox"], report)

    def test_start_delegates_to_existing_workflow(self):
        runtime = object.__new__(PortableAgentRuntime)
        with patch.object(WorkflowCoordinator, "start", return_value="task-1") as start:
            runtime.coordinator = object.__new__(WorkflowCoordinator)
            self.assertEqual(runtime.start("sample"), "task-1")
        start.assert_called_once_with("sample")
