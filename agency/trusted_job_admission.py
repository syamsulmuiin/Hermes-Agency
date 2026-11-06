"""Trusted-side job request admission; deliberately no privileged execution.

A validated worker credential authorizes only a bounded request record.
The root-operated systemd executor must never be exposed through this API.
"""
from .trusted import TrustedApprovalService
from .systemd_jobs import JOBS


class TrustedJobAdmission:
    def __init__(self, approval_service):
        if not isinstance(approval_service, TrustedApprovalService):
            raise TypeError("TrustedApprovalService required")
        self._approval = approval_service

    def admit(self, agent, job, worker_credential, approved=False):
        identity = self._approval._verify(worker_credential, "worker")
        if identity != agent:
            raise PermissionError("Worker identity mismatch")
        if type(job) is not str or job not in JOBS:
            raise PermissionError("Job not allowlisted")
        if approved is not True:
            raise PermissionError("Explicit approval required")
        return {"agent": agent, "job": job, "status": "admitted_not_executed",
                "execution_authorized": False}
