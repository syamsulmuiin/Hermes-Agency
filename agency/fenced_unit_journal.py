"""Durable root-owned ownership journal for opt-in fenced transient units.

The journal is committed and fsynced BEFORE systemd-run is invoked.
Recovery never trusts a client-supplied unit name. Production integration
requires independent systemd orchestration and crash tests.
"""
import os
import sqlite3
import stat

from .fenced_systemd_supervisor import _unit_name, stop_and_verify_unit


def _verify_store(path):
    if not os.path.isabs(path) or os.path.islink(path):
        raise PermissionError("Unsafe ownership journal path")
    parent = os.stat(os.path.dirname(path))
    if parent.st_uid != 0 or parent.st_mode & 0o022:
        raise PermissionError("Unsafe journal directory")
    if os.path.exists(path):
        info = os.lstat(path)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise PermissionError("Unsafe journal file")


def _connect(path):
    _verify_store(path)
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        os.chmod(path, 0o600)
        _verify_store(path)
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("""CREATE TABLE IF NOT EXISTS owned_units(
            unit TEXT PRIMARY KEY, state TEXT NOT NULL
            CHECK(state IN ('pending','verified')))""")
        return db
    except BaseException:
        db.close()
        raise


def register_before_launch(path, unit):
    """Persist ownership before any subprocess or transient unit starts."""
    _unit_name(unit)
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO owned_units(unit,state) VALUES (?,'pending')", (unit,))
        db.commit()
    # SQLite FULL synchronous commits database state; directory sync protects
    # initial journal creation across host power loss.
    directory = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def recover_owned_units(path, *, stop_unit=stop_and_verify_unit):
    """Stop and verify every pending unit, then durably mark it verified.

    No concurrent broker launch is permitted while this runs; the systemd
    startup gate must enforce that property externally.
    """
    with _connect(path) as db:
        pending = [row[0] for row in db.execute(
            "SELECT unit FROM owned_units WHERE state='pending' ORDER BY unit")]
        for unit in pending:
            _unit_name(unit)
            stop_unit(unit)
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE owned_units SET state='verified' WHERE unit=? AND state='pending'", (unit,))
            db.commit()
    return tuple(pending)
