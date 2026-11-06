"""Read-only discovery for independent container sandbox candidates.

No daemon/socket access, arbitrary commands, or fallback to host execution.
CLI presence alone never authorizes agent tools.
"""
import os
import shutil
import sys


def _candidate(name):
    binary = shutil.which(name)
    installed = bool(binary and os.path.isabs(binary))
    return {
        "cli_installed": installed,
        "validated": False,
        "reason": ("requires_isolation_and_daemon_policy_validation"
                   if installed else name + "_cli_missing"),
    }


def discover_backends():
    """Conservative, side-effect-free host inventory."""
    return {
        "platform": sys.platform,
        "backend": "disabled",
        "isolated_probe": False,
        "agent_tools_enabled": False,
        "reason": "no_validated_independent_backend",
        "candidates": {
            "docker": _candidate("docker"),
            "podman": _candidate("podman"),
        },
    }


def require_isolated_backend():
    """Deny execution until a validated sandbox runner is implemented."""
    raise RuntimeError("No validated independent sandbox backend; tool execution denied")
