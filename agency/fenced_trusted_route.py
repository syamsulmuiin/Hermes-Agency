"""Trusted-only fenced broker route for an already authenticated operator workflow.

This module is an in-process integration seam, not a CLI, worker socket, or
credential issuer. Deployment must inject a pre-provisioned candidate endpoint.
"""
import os

from .trusted_execution import TrustedAgentExecution
from .operator_control import operator_admission_lease

def execute_fenced_approved_job(boundary, approval_id, task_id, job,
                                worker_credential, lease_token, *,
                                broker_key_path, broker_socket_path):
    if not isinstance(boundary, TrustedAgentExecution):
        raise TypeError("TrustedAgentExecution required")
    if os.geteuid() == 0:
        raise PermissionError("Trusted caller must not run as root")
    if (not isinstance(broker_socket_path, str)
            or broker_socket_path != "/run/hermes-broker/fenced-candidate.sock"):
        raise PermissionError("Only pre-provisioned fenced broker endpoint allowed")
    if (not isinstance(broker_key_path, str)
            or broker_key_path != "/etc/hermes-broker/signing.key"):
        raise PermissionError("Only pre-provisioned broker key allowed")
    # Use the existing production admission lock for the entire grant submission.
    # A maintenance exclusive drain must reject this path before execution.
    with operator_admission_lease():
        return boundary.execute_operator_approved_job(
            approval_id, task_id, job, worker_credential, lease_token,
            broker_key_path, broker_socket_path)
