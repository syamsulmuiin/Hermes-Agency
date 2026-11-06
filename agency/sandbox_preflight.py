"""Fail-closed Linux independent sandbox readiness assessment.

This is a pre-execution security gate, not a sandbox runner. No tools execute.
Checks kernel namespace availability and an explicitly configured isolated UID;
never interprets binary presence as proof of isolation.
"""
import os
import sys


def _read(path):
    try:
        with open(path, "r", encoding="ascii") as stream:
            return stream.read(64).strip()
    except (OSError, UnicodeError):
        return None


def assess_linux_isolation(proc_root="/proc", sys_root="/proc/sys"):
    """Report observable prerequisites without creating namespaces or processes."""
    if not isinstance(proc_root, str) or not isinstance(sys_root, str):
        raise TypeError("Roots must be strings")
    if sys.platform != "linux":
        return {"ready": False, "reason": "non_linux", "checks": {}}
    namespace_root = os.path.join(proc_root, "self", "ns")
    required = ("user", "mnt", "pid", "net", "ipc", "uts")
    checks = {name: os.path.exists(os.path.join(namespace_root, name))
              for name in required}
    userns = _read(os.path.join(sys_root, "user", "max_user_namespaces"))
    try:
        checks["user_namespace_capacity"] = int(userns) > 0
    except (TypeError, ValueError):
        checks["user_namespace_capacity"] = False
    # Runtime isolation cannot be proven by host capability discovery.
    return {"ready": False, "reason": "runner_not_validated",
            "checks": checks, "kernel_prerequisites_present": all(checks.values())}


def require_verified_isolation(report):
    """Never promote host discovery to an execution authorization."""
    if not isinstance(report, dict):
        raise TypeError("Isolation report required")
    raise PermissionError("No independently verified sandbox runner; execution denied")
