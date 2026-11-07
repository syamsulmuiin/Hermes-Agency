"""Experimental systemd unit lifecycle guard; not production-wired.

A unit's identity must be unique and controlled by the root broker. This
guard is a building block, not a complete broker/sidecar crash protocol.
"""
import re
import subprocess
import time

_UNIT = re.compile(r"\Ahermes-fenced-[0-9a-f]{32}\.service\Z")


def _unit_name(unit):
    if type(unit) is not str or not _UNIT.fullmatch(unit):
        raise PermissionError("Unsafe fenced unit identity")
    return unit


def _systemctl(*args, timeout=5):
    try:
        return subprocess.run(
            ["/usr/bin/systemctl", "--system", *args],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PermissionError("Systemd unit control unavailable") from exc


def stop_and_verify_unit(unit, *, deadline_seconds=5):
    """Stop exact transient unit, require inactive/failed and no active job.

    If status cannot be established, fail closed; never report successful
    cleanup when systemd may still be running the unit.
    """
    _unit_name(unit)
    if type(deadline_seconds) not in (int, float) or not 0 < deadline_seconds <= 15:
        raise ValueError("Invalid stop deadline")
    stop = _systemctl("stop", unit)
    if stop.returncode != 0:
        raise PermissionError("Fenced systemd unit stop failed")
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        state = _systemctl(
            "show", unit, "--property=ActiveState",
            "--property=SubState", "--property=Job", "--property=MainPID")
        if state.returncode != 0:
            raise PermissionError("Fenced systemd unit status unavailable")
        fields = dict(line.split("=", 1) for line in state.stdout.decode(
            "ascii", "replace").splitlines() if "=" in line)
        if (fields.get("ActiveState") in ("inactive", "failed")
                and fields.get("Job") in ("", "0")
                and fields.get("MainPID") == "0"):
            return True
        time.sleep(0.05)
    raise PermissionError("Fenced systemd unit still active or unverified")
