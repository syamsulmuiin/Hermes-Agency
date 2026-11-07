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


def supervised_fenced_unit(job, grant_id, fence_socket, runner, *, journal_path=None):
    """Broker-side lifecycle boundary for an opt-in fixed-unit runner.

    The runner must monitor fence EOF while systemd-run is in progress and
    return only after the transient unit is no longer running. This wrapper
    verifies cleanup on both success and failure, and never reports success
    when stop/status verification fails. Not production-wired.
    """
    import hashlib
    from .systemd_jobs import JOBS
    if type(job) is not str or job not in JOBS:
        raise PermissionError("Job not allowlisted")
    if (type(grant_id) is not str or len(grant_id) != 64
            or any(ch not in "0123456789abcdef" for ch in grant_id)):
        raise PermissionError("Invalid signed grant identity")
    if not callable(runner):
        raise TypeError("Supervised unit runner required")
    unit = "hermes-fenced-" + hashlib.sha256(
        grant_id.encode("ascii")).hexdigest()[:32] + ".service"
    if journal_path is not None:
        from .fenced_unit_journal import register_before_launch
        register_before_launch(journal_path, unit)
    try:
        result = runner(job, fence_socket, unit)
    except BaseException:
        stop_and_verify_unit(unit)
        raise
    stop_and_verify_unit(unit)
    return result


def run_fenced_systemd_unit(job, fence_socket, unit):
    """Opt-in fixed-job systemd-run with live fence monitoring.

    A failure raises; supervised_fenced_unit always stops/verifies the unit.
    This does not protect against abrupt death of the root broker itself:
    a persistent watchdog/recovery unit is still required for production.
    """
    import os
    import select
    import socket
    from .systemd_jobs import JOBS, PROPERTIES
    _unit_name(unit)
    if type(job) is not str or job not in JOBS:
        raise PermissionError("Job not allowlisted")
    if not isinstance(fence_socket, socket.socket) or os.geteuid() != 0:
        raise PermissionError("Root broker and live fence required")
    argv = ["/usr/bin/systemd-run", "--system", "--wait", "--collect",
            "--quiet", "--unit=" + unit]
    for prop in PROPERTIES:
        argv.extend(("--property", prop))
    argv.extend(("--", *JOBS[job]))
    try:
        proc = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True,
            env={"PATH": "/usr/bin"})
    except OSError as exc:
        raise PermissionError("Systemd-run unavailable") from exc
    deadline = time.monotonic() + 12
    try:
        while time.monotonic() < deadline:
            readable, _, exceptional = select.select(
                [fence_socket], [], [fence_socket], 0.05)
            if readable or exceptional:
                try:
                    incoming = fence_socket.recv(
                        1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
                except OSError as exc:
                    raise PermissionError("Fence monitor unavailable") from exc
                if not incoming:
                    raise PermissionError("Fence disconnected during systemd job")
                raise PermissionError("Unexpected fence traffic during systemd job")
            status = proc.poll()
            if status is not None:
                if status != 0:
                    raise PermissionError("Systemd fixed job failed")
                return {"job": job, "exit_code": 0,
                        "stdout": "", "isolated_backend": "systemd",
                        "agent_tools_enabled": False}
        raise PermissionError("Systemd fixed job timeout")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
