"""Continuous, fail-closed single-VPS trusted service lifecycle.

Each request uses the existing authenticated one-shot listener. A supervisor
should restart the process on unexpected failure. No agent tools are exposed.
"""
import socket

from .single_vps_service import run_service


def serve_forever(socket_path, state_dir, database, key_dir, client_gid,
                  allowed_uids, secret, should_stop=None):
    """Serve sequential requests until explicitly stopped.

    The one-shot listener has a bounded accept timeout; idle periods do not
    terminate the service. All other errors fail closed for the supervisor.
    """
    if should_stop is None:
        should_stop = lambda: False
    if not callable(should_stop):
        raise TypeError("Stop predicate required")
    handled = 0
    while not should_stop():
        try:
            run_service(socket_path, state_dir, database, key_dir,
                        client_gid, allowed_uids, secret)
        except socket.timeout:
            continue
        handled += 1
    return handled
