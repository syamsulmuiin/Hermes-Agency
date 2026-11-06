"""Constrained real-process bubblewrap executor.

Only immutable built-in jobs are supported. This is not an agent shell or
authorization to run arbitrary code. Requires kernel namespace support.
"""
import os
import resource
import shutil
import subprocess
import sys

JOBS = {"noop": ("/usr/bin/true",), "identity": ("/usr/bin/id", "-u")}
MAX_OUTPUT = 4096


def _limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))


def run_isolated_job(job, timeout=5):
    """Run one fixed job in separate user/mount/PID/network namespaces.

    The result is returned only after bwrap exits successfully. If isolation
    is unavailable the job is denied; never execute directly on the host.
    """
    if type(job) is not str or job not in JOBS:
        raise PermissionError("Job not allowlisted")
    if type(timeout) not in (int, float) or not 1 <= timeout <= 10:
        raise ValueError("Invalid timeout")
    if sys.platform != "linux" or os.geteuid() == 0:
        raise PermissionError("Non-root Linux worker required")
    binary = shutil.which("bwrap")
    if not binary or not os.path.isabs(binary):
        raise PermissionError("Bubblewrap unavailable")
    if not os.path.islink("/bin") or os.readlink("/bin") != "usr/bin":
        raise PermissionError("Unsupported filesystem layout")
    for link, target in (("/lib", "usr/lib"), ("/lib64", "usr/lib64")):
        if not os.path.islink(link) or os.readlink(link) != target:
            raise PermissionError("Unsupported filesystem layout")
    argv = [
        binary, "--die-with-parent", "--new-session", "--unshare-all",
        "--clearenv", "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--chdir", "/", "--", *JOBS[job],
    ]
    try:
        result = subprocess.run(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env={}, timeout=timeout,
            close_fds=True, preexec_fn=_limits, check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise PermissionError("Isolated execution unavailable") from exc
    if result.returncode != 0:
        raise PermissionError("Isolated job failed or isolation denied")
    if len(result.stdout) > MAX_OUTPUT:
        raise PermissionError("Isolated output exceeds limit")
    return {"job": job, "exit_code": 0,
            "stdout": result.stdout.decode("utf-8", "replace"),
            "isolated_backend": "bubblewrap",
            "agent_tools_enabled": False}
