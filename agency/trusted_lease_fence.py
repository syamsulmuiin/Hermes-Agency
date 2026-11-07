"""Trusted-UID-owned lease transaction primitive for a future broker IPC.

No socket, execution, or root broker access is exposed here. A caller must
hold this context throughout the fixed-job execution handshake.
"""
from contextlib import contextmanager
import os
import sqlite3

from .broker_grants import verify_live_lease


@contextmanager
def fenced_lease(database, claims, *, now=None, timeout=5):
    """Hold a trusted SQLite writer lock until the caller exits.

    The transaction is always rolled back: its purpose is fencing, not state
    mutation. A revocation racing this context must wait for the lock.
    """
    if not isinstance(database, str) or not os.path.isabs(database):
        raise PermissionError("Absolute trusted database path required")
    if type(timeout) not in (int, float) or not 0 < timeout <= 5:
        raise ValueError("Invalid lease lock timeout")
    if not os.path.isfile(database):
        raise PermissionError("Trusted database unavailable")
    connection = sqlite3.connect(
        "file:" + database + "?mode=rw", uri=True,
        timeout=timeout, isolation_level=None,
    )
    try:
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise PermissionError("Trusted lease lock unavailable") from exc
        verify_live_lease(database, claims, now=now, connection=connection)
        yield
    finally:
        connection.rollback()
        connection.close()
