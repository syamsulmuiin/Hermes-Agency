"""Bounded, fail-closed sandbox probe validation.

Probes establish candidate diagnostics, not authority to execute agent tools.
The rootless probe and bubblewrap probe are fixed commands; no user payload
is ever forwarded to them. Unavailable backends remain unvalidated.
"""
import os
import sys

from .adaptive_sandbox import ORDER
from .linux_sandbox import run_isolated_probe
from .sandbox import sandbox_probe


def _reason(exc):
    if isinstance(exc, (PermissionError, OSError)):
        return "host_policy_or_isolation_denied"
    if isinstance(exc, (RuntimeError, ValueError)):
        message = str(exc).lower()
        if "not installed" in message:
            return "backend_missing"
        if "layout" in message:
            return "unsupported_layout"
        return "probe_failed"
    return "probe_failed"


def validate_candidates(timeout=5):
    """Attempt only existing fixed probes; never grant execution rights."""
    if type(timeout) not in (int, float) or not 1 <= timeout <= 10:
        raise ValueError("Invalid validation timeout")
    results = {name: {"probe_passed": False, "reason": "probe_not_implemented"}
               for name in ORDER}
    if sys.platform != "linux" or os.geteuid() == 0:
        for name in ("rootless_namespace", "bubblewrap"):
            results[name]["reason"] = "non_root_linux_worker_required"
    else:
        for name, probe in (("rootless_namespace", run_isolated_probe),
                            ("bubblewrap", sandbox_probe)):
            try:
                probe(timeout=timeout)
            except (PermissionError, RuntimeError, OSError, ValueError) as exc:
                results[name]["reason"] = _reason(exc)
            else:
                results[name] = {"probe_passed": True,
                                 "reason": "probe_only_executor_not_verified"}
    return {"candidates": results, "selected": None,
            "agent_tools_enabled": False,
            "reason": "no_attested_executor"}


def require_validated_executor(report):
    """Probe results, even successful ones, cannot authorize arbitrary tools."""
    if not isinstance(report, dict):
        raise TypeError("Validation report required")
    raise PermissionError("No attested sandbox executor; execution denied")
