"""Opt-in root staging broker composition; never invoked by production service.

Trusted peer must run serve_fence_connection with a cleanup_before_release
callback that stops/verifies the exact operator-derived unit. An independent
watchdog must recover the journal if either process dies. This entrypoint
never issues approvals or grants and cannot be called by an agent worker.
"""
import hashlib
import os

from .broker_grants import verify_broker_grant
from .fenced_staging_serialization import staging_launch
from .fenced_systemd_supervisor import (
    run_fenced_systemd_unit, stop_and_verify_unit, supervised_fenced_unit,
)
from .fenced_unit_journal import recover_owned_units
from .trusted_lease_ipc import broker_fenced_job


def unit_for_grant(grant_id):
    """Derive the sole permitted unit identity from a verified grant ID."""
    if (type(grant_id) is not str or len(grant_id) != 64
            or any(c not in "0123456789abcdef" for c in grant_id)):
        raise PermissionError("Invalid grant identifier")
    return "hermes-fenced-" + hashlib.sha256(
        grant_id.encode("ascii")).hexdigest()[:32] + ".service"


def staging_broker_job(conn, grant, verification_key, journal, *,
                       runner=run_fenced_systemd_unit, ledger=None):
    """Serialize admission, durable registration, execution and verification.

    This function requires a separately provisioned trusted IPC peer and
    independent recovery watchdog. On any error, pending journal state is
    intentionally preserved for fail-closed recovery. No production wiring.
    """
    if os.geteuid() != 0:
        raise PermissionError("Staging root broker required")
    if not callable(runner):
        raise TypeError("Fenced systemd runner required")
    claims = verify_broker_grant(grant, verification_key)
    unit = unit_for_grant(claims["id"])

    def launch():
        if ledger is not None:
            from .fenced_grant_ledger import consume_fenced_grant
            consume_fenced_grant(ledger, grant, verification_key)
        def execute(job):
            if job != claims["job"]:
                raise PermissionError("Grant job mismatch")
            return supervised_fenced_unit(
                job, claims["id"], conn, runner)
        try:
            result = broker_fenced_job(conn, grant, execute)
        except BaseException:
            if ledger is not None:
                from .fenced_grant_ledger import finish_fenced_grant
                finish_fenced_grant(ledger, claims["id"], verified=False)
            raise
        # Still under staging launch lock. Do not mark verified until the
        # trusted peer has acknowledged release after stop verification.
        recovered = recover_owned_units(journal, stop_unit=stop_and_verify_unit)
        if recovered != (unit,):
            raise PermissionError("Unexpected journal recovery set")
        if ledger is not None:
            from .fenced_grant_ledger import finish_fenced_grant
            finish_fenced_grant(ledger, claims["id"], verified=True)
        return result

    return staging_launch(journal, unit, launch)
