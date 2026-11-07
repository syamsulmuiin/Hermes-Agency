"""Trusted-process-only adapter for an already authenticated approval workflow.

This is deliberately NOT a worker-facing socket endpoint. The caller must
supply an existing TrustedApprovalService, verified worker credential and
lease token; the approval decision must already have been made by an approver.
"""
import os
import stat

from .broker_grants import issue_broker_grant
from .signed_broker_service import submit_signed_grant


def _trusted_key(path):
    if os.geteuid() == 0 or not os.path.isabs(path):
        raise PermissionError("Non-root trusted process and absolute key path required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_gid != os.getegid()
                or stat.S_IMODE(info.st_mode) != 0o640 or info.st_uid != 0
                or info.st_nlink != 1):
            raise PermissionError("Invalid trusted broker signing key")
        key = os.read(fd, 65)
        if len(key) != 64:
            raise PermissionError("Invalid broker signing key length")
        return key
    finally:
        os.close(fd)


def execute_approved_job(service, approval, task_id, job, worker_credential,
                         lease_token, key_path, socket_path):
    """Consume one real approved grant and submit to signed-only broker.

    No credential issuance, approval decision or arbitrary command execution.
    A failed submission consumes the grant (fail closed).
    """
    key = _trusted_key(key_path)
    envelope = issue_broker_grant(service, approval, task_id, job,
                                  worker_credential, lease_token, key)
    return submit_signed_grant(socket_path, envelope)
