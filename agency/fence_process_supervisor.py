"""Opt-in subprocess supervisor bound to the trusted lease-fence socket.

Not connected to the production systemd runner. A systemd transient unit
requires its own unit-lifetime cancellation and verification mechanism.
"""
import os
import select
import signal
import socket
import subprocess
import time


def _terminate_group(process):
    """Kill the dedicated process group, then reap; never signal a shared group."""
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def run_fence_supervised_subprocess(argv, fence_socket, *, timeout=8):
    """Run a fixed argv while watching IPC EOF; fail closed on loss or timeout.

    The caller must have completed the signed-grant lock handshake before
    calling this function. Only a dedicated process group is eligible.
    """
    if (not isinstance(argv, tuple) or not argv or
            any(type(arg) is not str or not arg.startswith("/")
                for arg in argv[:1]) or
            any(type(arg) is not str or not arg for arg in argv) or
            type(timeout) not in (int, float) or not 0 < timeout <= 20):
        raise ValueError("Invalid supervised command")
    if not isinstance(fence_socket, socket.socket):
        raise TypeError("Fence socket required")
    process = subprocess.Popen(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PermissionError("Supervised job timeout")
            readable, _, exceptional = select.select(
                [fence_socket], [], [fence_socket], min(remaining, 0.05))
            if exceptional or readable:
                try:
                    peek = fence_socket.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
                except (OSError, BlockingIOError) as exc:
                    raise PermissionError("Fence monitoring failed") from exc
                if not peek:
                    raise PermissionError("Trusted fence disconnected")
                raise PermissionError("Unexpected trusted fence traffic")
            code = process.poll()
            if code is not None:
                # Check the socket again immediately before accepting completion.
                readable, _, exceptional = select.select(
                    [fence_socket], [], [fence_socket], 0)
                if readable or exceptional:
                    raise PermissionError("Fence lost at job completion")
                if code != 0:
                    raise PermissionError("Supervised job failed")
                return {"exit_code": 0}
    finally:
        _terminate_group(process)
