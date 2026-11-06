"""Operator acceptance test of real systemd sandbox boundaries.

Runs fixed Python assertions inside the same systemd properties as the job
executor. This is a deployment gate, not an agent-accessible API.
"""
import json
import os
import shutil
import subprocess
import sys

from .systemd_jobs import PROPERTIES

CHECK = r"""
import json, os, socket
out = {}
out["non_root"] = os.geteuid() != 0
out["host_shadow_unreadable"] = not os.access("/etc/shadow", os.R_OK)
out["root_home_inaccessible"] = not os.access("/root", os.R_OK)
out["usr_not_writable"] = not os.access("/usr", os.W_OK)
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError:
    out["inet_socket_denied"] = True
else:
    out["inet_socket_denied"] = False
print(json.dumps(out, sort_keys=True))
"""


def verify_systemd_isolation(timeout=15):
    if type(timeout) not in (int, float) or not 2 <= timeout <= 30:
        raise ValueError("Invalid timeout")
    if sys.platform != "linux" or os.geteuid() != 0:
        raise PermissionError("Operator root required")
    binary = shutil.which("systemd-run")
    if not binary or not os.path.isabs(binary):
        raise PermissionError("Systemd unavailable")
    argv = [binary, "--system", "--wait", "--collect", "--pipe", "--quiet"]
    for prop in PROPERTIES:
        argv.extend(("--property", prop))
    argv.extend(("--", "/usr/bin/python3", "-I", "-c", CHECK))
    try:
        result = subprocess.run(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env={"PATH": "/usr/bin"},
            timeout=timeout, close_fds=True, check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise PermissionError("Systemd acceptance execution unavailable") from exc
    if result.returncode or len(result.stdout) > 4096:
        raise PermissionError("Systemd acceptance probe failed")
    try:
        checks = json.loads(result.stdout)
    except (ValueError, UnicodeError) as exc:
        raise PermissionError("Invalid acceptance result") from exc
    expected = {"non_root", "host_shadow_unreadable",
                "root_home_inaccessible", "usr_not_writable",
                "inet_socket_denied"}
    if not isinstance(checks, dict) or set(checks) != expected:
        raise PermissionError("Incomplete acceptance evidence")
    if any(checks[key] is not True for key in expected):
        raise PermissionError("Systemd isolation acceptance denied")
    return {"backend": "systemd", "accepted": True, "checks": checks,
            "agent_tools_enabled": False}
