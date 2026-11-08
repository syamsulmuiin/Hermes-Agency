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


def load(path):
    p = Path(path)
    info = p.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16384:
        raise PermissionError("Unsafe deployment manifest")
    with p.open("r", encoding="utf-8") as stream:
        return validate(json.load(stream))


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
    result = run([systemctl, "show", "--property=Version"],
                 capture_output=True, text=True, timeout=5, check=False)
    if result.returncode:
        raise PermissionError("systemd manager unavailable")
    return {"schema": "hermes-runtime-resolution-v1",
            "systemctl": systemctl, "uids": users, "gids": groups,
            "paths": dict(manifest["paths"]), "units": dict(manifest["units"]),
            "identity_resolved": True, "runtime_behavior_attested": False,
            "sandbox_authorized": False, "cutover_authorized": False}
