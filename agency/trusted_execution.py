"""Trusted in-process workflow submission boundary.

Caller credentials are verified by TrustedApprovalService. The signing key and
credential issuance MUST remain in a separate trusted process boundary.
No network API or tool execution is exposed here.
"""
from .portable_runtime import PortableAgentRuntime
from .trusted import TrustedApprovalService


class TrustedAgentExecution:
    def __init__(self, runtime, approval_service):
        if not isinstance(runtime, PortableAgentRuntime):
            raise TypeError("PortableAgentRuntime required")
        if not isinstance(approval_service, TrustedApprovalService):
            raise TypeError("TrustedApprovalService required")
        if runtime.coordinator.store is not approval_service.store:
            raise ValueError("Services must share the same store")
        self._runtime = runtime
        self._approval_service = approval_service

    def submit_stage(self, task_id, agent, result, worker_credential):
        """Accept a stage only when the verified worker identity matches agent.

        This checks role and identity but is NOT a remote authentication API.
        The worker credential must be issued after external authentication.
        """
        identity = self._approval_service._verify(worker_credential, "worker")
        if identity != agent:
            raise PermissionError("Worker identity does not match stage agent")
        return self._runtime.submit_stage_result(task_id, agent, result)

    def capabilities(self):
        return self._runtime.capabilities()
