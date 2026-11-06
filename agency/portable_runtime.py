"""Portable, tool-free workflow access.

The workflow coordinator works even when no sandbox backend exists.
This adapter deliberately exposes no shell, filesystem, network, or tool API.
"""
from .orchestrator import WorkflowCoordinator
from .independent_sandbox import discover_backends


class PortableAgentRuntime:
    def __init__(self, coordinator: WorkflowCoordinator):
        if not isinstance(coordinator, WorkflowCoordinator):
            raise TypeError("WorkflowCoordinator required")
        self.coordinator = coordinator

    def capabilities(self):
        sandbox = discover_backends()
        return {
            "workflow_available": True,
            "tool_execution_available": False,
            "sandbox": sandbox,
        }

    def start(self, title):
        return self.coordinator.start(title)

    def snapshot(self, task_id):
        return self.coordinator.snapshot(task_id)

    def submit_stage_result(self, task_id, agent, result):
        """Internal-only: caller authentication is not implemented."""
        return self.coordinator.advance(task_id, agent, result)
