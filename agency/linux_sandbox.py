"""Rootless Linux namespace sandbox for a fixed, non-tool isolation probe.

No Docker, Podman, Bubblewrap, host shell or agent-supplied code. This
runner deliberately exposes only a built-in probe until escape testing and
a separately authorized tool policy are implemented.
"""
import ctypes
import json
import os
import resource
import signal
import subprocess
import sys
import tempfile

CLONE_NEWNS = 0x00020000
CLONE_NEWUTS = 0x04000000
CLONE_NEWIPC = 0x08000000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
MS_REC = 16384
MS_PRIVATE = 1 << 18
LIBC = ctypes.CDLL(None, use_errno=True)


def _call(name, *args):
    fn = getattr(LIBC, name)
    if fn(*args) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), name)


def _write(path, value):
    with open(path, "w", encoding="ascii") as stream:
        stream.write(value)


def _limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))


def _probe():
    # Must be run only after namespace, chroot, and PID isolation.
    visible = os.listdir("/")
    if visible:
        raise PermissionError("Sandbox root is not empty")
    if os.path.exists("/etc/passwd") or os.path.exists("/proc/1/root"):
        raise PermissionError("Host filesystem visible")
    return {"root_empty": True, "host_files_absent": True,
            "pid": os.getpid(), "uid": os.getuid()}


def _child():
    if sys.platform != "linux" or os.geteuid() == 0:
        raise PermissionError("Rootless Linux worker required")
    _limits()
    # Capture host IDs before entering the unmapped user namespace.
    host_uid, host_gid = os.getuid(), os.getgid()
    _call("unshare", CLONE_NEWUSER)
    _write("/proc/self/setgroups", "deny")
    _write("/proc/self/uid_map", "0 %d 1\n" % os.getuid())
    _write("/proc/self/gid_map", "0 %d 1\n" % os.getgid())
    _call("unshare", CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWIPC | CLONE_NEWNET | CLONE_NEWPID)
    _call("mount", ctypes.c_void_p(), ctypes.c_char_p(b"/"),
          ctypes.c_void_p(), MS_REC | MS_PRIVATE, ctypes.c_void_p())
    with tempfile.TemporaryDirectory(prefix="hermes-isolation-") as root:
        _call("mount", ctypes.c_char_p(b"tmpfs"), ctypes.c_char_p(os.fsencode(root)),
              ctypes.c_char_p(b"tmpfs"), 0,
              ctypes.c_char_p(b"size=8m,mode=0700"))
        try:
            pid = os.fork()
            if pid == 0:
                try:
                    os.chroot(root)
                    os.chdir("/")
                    # Drop capabilities inherited inside user namespace via
                    # no_new_privs; not a complete seccomp policy.
                    _call("prctl", 38, 1, 0, 0, 0)
                    result = _probe()
                    if result["pid"] != 1:
                        raise PermissionError("PID namespace not effective")
                    print(json.dumps(result), flush=True)
                    os._exit(0)
                except BaseException:
                    os._exit(111)
            _, status = os.waitpid(pid, 0)
            if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
                raise PermissionError("Isolated probe failed")
        finally:
            _call("umount2", ctypes.c_char_p(os.fsencode(root)), 2)


def run_isolated_probe(timeout=8):
    """Return probe evidence; never fall back to unsandboxed execution."""
    if type(timeout) not in (int, float) or not 1 <= timeout <= 30:
        raise ValueError("Invalid timeout")
    if sys.platform != "linux" or os.geteuid() == 0:
        raise PermissionError("Non-root Linux caller required")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "agency.linux_sandbox", "--internal-probe"],
            capture_output=True, text=True, timeout=timeout, check=False,
            start_new_session=True, close_fds=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise PermissionError("Sandbox probe timed out") from exc
    if result.returncode != 0:
        raise PermissionError("Sandbox isolation unavailable or failed")
    try:
        evidence = json.loads(result.stdout.strip())
    except (ValueError, TypeError) as exc:
        raise PermissionError("Invalid sandbox probe evidence") from exc
    if evidence != {"root_empty": True, "host_files_absent": True, "pid": 1, "uid": 0}:
        raise PermissionError("Sandbox evidence mismatch")
    return evidence


if __name__ == "__main__":
    if sys.argv[1:] != ["--internal-probe"]:
        raise SystemExit(2)
    try:
        _child()
    except BaseException:
        raise SystemExit(1)
