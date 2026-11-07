"""Explicit staging-only broker/peer launcher for isolated /run fixtures.

This module does not install systemd services or accept agent requests.
A separate root-owned systemd watchdog must run recovery on supervisor death.
"""
import multiprocessing
import os
import socket
import threading

from .fenced_staging_broker import staging_broker_job
from .fenced_staging_peer import root_stop_session, trusted_peer_session


def _staging_path(path):
    if (type(path) is not str or not path.startswith("/run/hermes-staging/")
            or os.path.normpath(path) != path):
        raise PermissionError("Only isolated /run/hermes-staging paths allowed")
    return path


def _peer_child(peer, control, broker, root_control, database, key, uid, gid):
    broker.close()
    root_control.close()
    try:
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
        trusted_peer_session(peer, control, database, key)
    finally:
        peer.close()
        control.close()


def run_staging_session(grant, key, journal, database, *, trusted_uid,
                        trusted_gid, runner=None):
    """Start a non-root trusted peer and concurrent root stop controller.

    Root controller runs in a thread because it must serve stop requests
    while the root broker waits for trusted IPC completion. The peer is
    forked before any controller thread starts. A caller must arrange
    independent systemd recovery for SIGKILL of this root process.
    """
    if os.geteuid() != 0:
        raise PermissionError("Root staging operator required")
    _staging_path(journal)
    _staging_path(database)
    if (type(trusted_uid) is not int or trusted_uid <= 0
            or type(trusted_gid) is not int or trusted_gid <= 0):
        raise PermissionError("Dedicated non-root staging identity required")
    if not isinstance(key, bytes) or len(key) < 32:
        raise PermissionError("Staging signing key required")
    if runner is None:
        from .fenced_systemd_supervisor import run_fenced_systemd_unit
        runner = run_fenced_systemd_unit
    broker, peer = socket.socketpair()
    root_control, trusted_control = socket.socketpair()
    process = multiprocessing.get_context("fork").Process(
        target=_peer_child,
        args=(peer, trusted_control, broker, root_control,
              database, key, trusted_uid, trusted_gid))
    controller_errors = []
    def control():
        try:
            root_stop_session(root_control, grant, key)
        except BaseException as exc:
            controller_errors.append(exc)
            # Force trusted cleanup to fail closed if stop cannot be verified.
            root_control.shutdown(socket.SHUT_RDWR)
    try:
        process.start()
        peer.close()
        trusted_control.close()
        controller = threading.Thread(target=control, daemon=True)
        controller.start()
        try:
            result = staging_broker_job(
                broker, grant, key, journal, runner=runner)
        finally:
            broker.close()
            controller.join(15)
            if controller.is_alive():
                root_control.shutdown(socket.SHUT_RDWR)
                raise PermissionError("Root stop controller did not finish")
        process.join(5)
        if process.is_alive() or process.exitcode != 0 or controller_errors:
            raise PermissionError("Trusted peer or stop controller failed")
        return result
    finally:
        for conn in (broker, peer, root_control, trusted_control):
            conn.close()
        if process.pid is not None:
            if process.is_alive():
                process.kill()
            process.join(3)
