"""Independent sandbox backend discovery.

This is a read-only capability inventory, not a command executor. A Docker
CLI is not proof of safe Docker daemon access. Never fall back to host shell.
"""
import os
import shutil
import sys


def discover_backends():
    """Return conservative readiness without contacting a privileged daemon."""
    docker = shutil.which("docker")
    docker_cli = bool(docker and os.path.isabs(docker))
    return {
        "platform": sys.platform,
        "backend": "disabled",
        "isolated_probe": False,
        "agent_tools_enabled": False,
        "reason": "no_validated_independent_backend",
        "candidates": {
            "docker": {
                "cli_installed": docker_cli,
                "validated": False,
                "reason": "requires_isolation_and_daemon_policy_validation"
                if docker_cli else "docker_cli_missing",
            },
        },
    }


def require_isolated_backend():
    """Fail closed until a separately validated isolated executor exists."""
    raise RuntimeError("No validated independent sandbox backend; tool execution denied")
