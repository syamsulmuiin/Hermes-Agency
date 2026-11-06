"""Operator-only systemd sandbox executor for fixed diagnostic jobs.

Never callable by the unprivileged agent worker or trusted service. A root
operator may run these fixed commands through systemd transient services.
This is a constrained execution backend, not general agent tool support.
"""
import os
import shutil
import subprocess
import sys

JOBS = {"noop": ("/usr/bin/true",), "identity": ("/usr/bin/id", "-u")}
PROPERTIES = (
    "Type=exec", "DynamicUser=yes", "NoNewPrivileges=yes",
    "PrivateNetwork=yes", "PrivateTmp=yes", "PrivateDevices=yes",
    "ProtectSystem=strict", "ProtectHome=yes", "ProtectKernelTunables=yes",
    "ProtectKernelModules=yes", "ProtectKernelLogs=yes",
    "ProtectControlGroups=yes", "ProtectClock=yes",
    "RestrictSUIDSGID=yes", "LockPersonality=yes",
    "RestrictRealtime=yes", "MemoryDenyWriteExecute=yes",
    "CapabilityBoundingSet=", "AmbientCapabilities=",
    "RestrictAddressFamilies=AF_UNIX",
    "SystemCallArchitectures=native", "UMask=0077",
    "MemoryMax=128M", "TasksMax=16", "CPUQuota=50%",
    "RuntimeMaxSec=8s", "LimitCORE=0", "LimitFSIZE=0",
    "WorkingDirectory=/", "Environment=PATH=/usr/bin",
)


def run_systemd_job(job, timeout=12):
    """Execute a fixed command in a sandboxed transient system service.

    Root invocation is an operator deployment/test boundary, never an
    invitation to grant root or sudo to an agent. A systemd failure denies.
    """
    if type(job) is not str or job not in JOBS:
        raise PermissionError("Job not allowlisted")
    if type(timeout) not in (int, float) or not 2 <= timeout <= 20:
        raise ValueError("Invalid timeout")
    if sys.platform != "linux" or os.geteuid() != 0:
        raise PermissionError("Operator root required; agent access denied")
    binary = shutil.which("systemd-run")
    if not binary or not os.path.isabs(binary):
        raise PermissionError("Systemd runner unavailable")
    argv = [binary, "--system", "--wait", "--collect", "--pipe", "--quiet"]
    for prop in PROPERTIES:
        argv.extend(("--property", prop))
    argv.extend(("--", *JOBS[job]))
    try:
        result = subprocess.run(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env={"PATH": "/usr/bin"},
            timeout=timeout, close_fds=True, check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise PermissionError("Systemd sandbox execution unavailable") from exc
    if result.returncode != 0:
        raise PermissionError("Systemd sandbox failed or host policy denied")
    if len(result.stdout) > 4096:
        raise PermissionError("Sandbox output limit exceeded")
    return {"job": job, "exit_code": 0,
            "stdout": result.stdout.decode("utf-8", "replace"),
            "isolated_backend": "systemd", "agent_tools_enabled": False}
