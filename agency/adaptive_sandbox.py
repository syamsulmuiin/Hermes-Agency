"""Portable, fail-closed isolation candidate selection.

Discovery is not authorization. No command, daemon or agent tool is launched.
A backend may be selected only from explicitly validated evidence supplied by
the caller; selection still does not grant tool execution permission.
"""
from .independent_sandbox import discover_backends
from .sandbox_preflight import assess_linux_isolation

ORDER = ("rootless_namespace", "bubblewrap", "systemd", "podman", "docker")


def inventory():
    container = discover_backends()
    linux = assess_linux_isolation()
    return {
        "platform": container["platform"],
        "candidates": {
            "rootless_namespace": {
                "available_hint": bool(linux.get("kernel_prerequisites_present")),
                "validated": False,
            },
            "bubblewrap": {"available_hint": False, "validated": False},
            "systemd": {"available_hint": False, "validated": False},
            "podman": {
                "available_hint": container["candidates"]["podman"]["cli_installed"],
                "validated": False,
            },
            "docker": {
                "available_hint": container["candidates"]["docker"]["cli_installed"],
                "validated": False,
            },
        },
        "agent_tools_enabled": False,
        "selected": None,
        "reason": "no_backend_verified",
    }


def choose_backend(evidence):
    """Accept only complete policy-approved evidence, never availability hints."""
    if not isinstance(evidence, dict) or set(evidence) != {"validated", "policy_approved"}:
        raise PermissionError("Backend validation and policy approval required")
    validated, approved = evidence["validated"], evidence["policy_approved"]
    if not isinstance(validated, dict) or not isinstance(approved, dict):
        raise PermissionError("Invalid isolation evidence")
    if set(validated) != set(ORDER) or set(approved) != set(ORDER):
        raise PermissionError("Incomplete isolation evidence")
    if any(type(value) is not bool for value in (*validated.values(), *approved.values())):
        raise PermissionError("Invalid isolation evidence values")
    # Caller-controlled dictionaries are not attestations; do not authorize
    # execution based on this result. This is a pure planning helper only.
    for backend in ORDER:
        if validated[backend] and approved[backend]:
            return {"candidate": backend, "agent_tools_enabled": False,
                    "reason": "planning_only_untrusted_evidence"}
    return {"candidate": None, "agent_tools_enabled": False,
            "reason": "no_approved_validated_candidate"}


def require_adaptive_executor():
    raise PermissionError("No attested adaptive sandbox executor; execution denied")
