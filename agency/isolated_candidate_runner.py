"""Test-only runner: identity holds a real isolated transient unit for SIGKILL."""
import os
import time

from .fenced_staging_launcher import run_staging_session
from .fenced_systemd_supervisor import run_fenced_systemd_unit
from .real_systemd_crash_acceptance import launch, await_active


def _runner(job, fence, unit):
    if job != "identity":
        return run_fenced_systemd_unit(job, fence, unit)
    if not os.path.isfile("/run/hermes-staging/allow-hold-test"):
        raise PermissionError("Isolated hold test marker absent")
    launch(unit)
    await_active(unit)
    # Only the test-specific identity grant holds an active transient unit.
    # The acceptance harness kills the broker; independent PID1 recovery
    # must stop this unit. Never execute this runner in production profile.
    while True:
        time.sleep(0.1)


def isolated_session(grant, key, journal, database, *, trusted_uid,
                     trusted_gid, ledger, isolated_candidate=False,
                     production_candidate=False):
    if not isolated_candidate or production_candidate:
        raise PermissionError("Test runner restricted to isolated profile")
    return run_staging_session(
        grant, key, journal, database, trusted_uid=trusted_uid,
        trusted_gid=trusted_gid, ledger=ledger, isolated_candidate=True,
        runner=_runner)
