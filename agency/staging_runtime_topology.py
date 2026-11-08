"""Staging topology contract: reject any unverified separation claims."""
from pathlib import PurePosixPath


def validate_topology(config):
    required = {"vm_id", "pid1", "rootfs", "journal", "socket", "admission_lock",
                "freeze", "trusted_user", "worker_user"}
    if not isinstance(config, dict) or set(config) != required:
        raise PermissionError("Incomplete staging topology")
    if not all(isinstance(v, str) and v for v in config.values()):
        raise PermissionError("Invalid staging topology")
    if config["pid1"] != "systemd":
        raise PermissionError("Independent systemd PID1 required")
    paths = ("rootfs", "journal", "socket", "admission_lock", "freeze")
    for key in paths:
        path = PurePosixPath(config[key])
        if not path.is_absolute() or ".." in path.parts or str(path) == "/":
            raise PermissionError("Unsafe staging path")
    if len({config[k] for k in paths}) != len(paths):
        raise PermissionError("Staging path alias")
    if config["trusted_user"] == config["worker_user"]:
        raise PermissionError("Staging identity separation required")
    return {"topology_well_formed": True, "independent_vm_attested": False,
            "isolated_pid1_attested": False, "state_separation_attested": False,
            "execute_authorized": False, "production_mutated": False}
