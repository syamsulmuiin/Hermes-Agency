"""Opt-in staging stop-before-unlock protocol between trusted peer and root.

The trusted process may request only the unit derived from the verified
signed grant. The root supervisor must verify stop before acknowledging.
Independent journal recovery remains mandatory on root supervisor death.
"""
import json
import os

from .broker_grants import verify_broker_grant
from .fenced_staging_broker import unit_for_grant
from .fenced_systemd_supervisor import stop_and_verify_unit
from .trusted_lease_ipc import _read_line, _send, serve_fence_connection


def trusted_peer_session(conn, control, database, verification_key, *,
                         root_uid=0, now=None):
    """Non-root trusted endpoint; no systemd privileges or client unit names."""
    if os.geteuid() == 0:
        raise PermissionError("Trusted peer must be non-root")

    def cleanup(claims):
        unit = unit_for_grant(claims["id"])
        _send(control, {"op": "stop", "unit": unit})
        response = json.loads(_read_line(control))
        if response != {"status": "verified", "unit": unit}:
            raise PermissionError("Root stop verification unavailable")

    return serve_fence_connection(
        conn, database, verification_key, root_uid=root_uid, now=now,
        cleanup_before_release=cleanup)


def root_stop_session(control, grant, verification_key, *,
                      stop_unit=stop_and_verify_unit):
    """Root-owned control socket, bound to one signed grant and exact unit."""
    if os.geteuid() != 0:
        raise PermissionError("Root supervisor required")
    claims = verify_broker_grant(grant, verification_key)
    unit = unit_for_grant(claims["id"])
    request = json.loads(_read_line(control))
    if request != {"op": "stop", "unit": unit}:
        raise PermissionError("Unauthorized stop request")
    stop_unit(unit)
    _send(control, {"status": "verified", "unit": unit})
    return unit
