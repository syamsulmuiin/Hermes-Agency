"""Strict, non-authorizing deployment manifest and host runtime resolver."""
import json
import os
from pathlib import Path
import pwd
import grp
import re
import shutil
import stat
import subprocess

FIELDS = ("snapshot", "admission_lock", "freeze_marker", "operator_socket")
UNITS = ("agency", "broker", "sidecar", "candidate_broker", "candidate_recovery")
IDENTITIES = ("trusted_user", "trusted_group", "worker_user")
_NAME = re.compile(r"^[a-z_][a-z0-9_-]{0,63}$")
_UNIT = re.compile(r"^[a-zA-Z0-9_.@-]{1,128}[.]service$")


def _path(value):
    if not isinstance(value, str) or not value.startswith("/") or "\\x00" in value:
        raise ValueError("Path must be absolute")
    p = Path(value)
    if ".." in p.parts or str(p) != value or value == "/":
        raise ValueError("Path is not canonical")
    return value


def validate(data):
    if not isinstance(data, dict) or set(data) != {"schema", "paths", "units", "identities"}:
        raise ValueError("Unexpected manifest fields")
    if data["schema"] != "hermes-deployment-v1":
        raise ValueError("Unsupported manifest schema")
    for key, fields in (("paths", FIELDS), ("units", UNITS), ("identities", IDENTITIES)):
        obj = data[key]
        if not isinstance(obj, dict) or set(obj) != set(fields):
            raise ValueError("Missing or unexpected " + key)
    for value in data["paths"].values():
        _path(value)
    if len(set(data["paths"].values())) != len(FIELDS):
        raise ValueError("Deployment paths must be distinct")
    for value in data["units"].values():
        if not isinstance(value, str) or not _UNIT.fullmatch(value):
            raise ValueError("Invalid unit name")
    for value in data["identities"].values():
        if not isinstance(value, str) or not _NAME.fullmatch(value):
            raise ValueError("Invalid identity")
    return data


def _trusted_chain(path):
    """Reject writable or linked ancestors of a privileged configuration path."""
    current = Path("/")
    for component in Path(path).parts[1:]:
        current = current / component
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError("Untrusted path component: " + str(current))
    return current


def load(path):
    """Read a root-controlled manifest from one pinned file descriptor."""
    p = Path(_path(os.fspath(path)))
    _trusted_chain(p.parent)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if not hasattr(os, "O_NOFOLLOW"):
        raise PermissionError("Secure manifest open unavailable")
    fd = os.open(p, flags | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or info.st_nlink != 1
                or info.st_size > 16384):
            raise PermissionError("Unsafe deployment manifest")
        raw = os.read(fd, 16385)
        if len(raw) > 16384:
            raise PermissionError("Deployment manifest too large")
        # Detect path replacement during the read, including symlink swaps.
        after = p.lstat()
        if (after.st_dev, after.st_ino) != (info.st_dev, info.st_ino):
            raise PermissionError("Deployment manifest replaced")
        _trusted_chain(p.parent)
        return validate(json.loads(raw.decode("utf-8")))
    finally:
        os.close(fd)


def _trusted_systemctl(path):
    """Verify systemctl and its path cannot be replaced by untrusted users."""
    if not os.path.isabs(path):
        raise PermissionError("systemctl path must be absolute")
    resolved = os.path.realpath(path)
    _trusted_chain(resolved)
    info = os.stat(resolved)
    if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
        raise PermissionError("Invalid systemctl executable")
    return resolved


def resolve(manifest, which=shutil.which, run=subprocess.run):
    """Resolve current host identities and systemctl; never provision anything."""
    validate(manifest)
    systemctl = which("systemctl")
    if not systemctl or not os.path.isabs(systemctl):
        raise PermissionError("systemctl unavailable")
    identities = manifest["identities"]
    users = {key: pwd.getpwnam(identities[key]).pw_uid
             for key in ("trusted_user", "worker_user")}
    groups = {"trusted_group": grp.getgrnam(identities["trusted_group"]).gr_gid}
    if users["trusted_user"] == 0 or users["worker_user"] == 0:
        raise PermissionError("Trusted and worker users must be unprivileged")
    systemctl = _trusted_systemctl(systemctl)
    result = run([systemctl, "show", "--property=Version"],
                 capture_output=True, text=True, timeout=5, check=False)
    if result.returncode:
        raise PermissionError("systemd manager unavailable")
    return {"schema": "hermes-runtime-resolution-v1",
            "systemctl": systemctl, "uids": users, "gids": groups,
            "paths": dict(manifest["paths"]), "units": dict(manifest["units"]),
            "identity_resolved": True, "runtime_behavior_attested": False,
            "sandbox_authorized": False, "cutover_authorized": False}
