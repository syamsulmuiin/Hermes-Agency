"""Atomic one-time signed grant admission for a fenced root broker.

The root-owned SQLite ledger records a grant as consumed before any transient
unit may launch. A crashed or denied attempt is never automatically replayed.
"""
import sqlite3

from .broker_grants import verify_broker_grant
from .systemd_broker import verify_private_ledger


def consume_fenced_grant(ledger, grant, verification_key, *, now=None):
    claims = verify_broker_grant(grant, verification_key, now=now)
    verify_private_ledger(ledger)
    db = sqlite3.connect(ledger, timeout=5, isolation_level=None)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS signed_grant_consumptions(
            grant_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
            worker TEXT NOT NULL, lease_generation INTEGER NOT NULL,
            job TEXT NOT NULL, approval_id TEXT NOT NULL, status TEXT NOT NULL)""")
        try:
            db.execute("INSERT INTO signed_grant_consumptions VALUES (?,?,?,?,?,?,?)",
                       (claims["id"], claims["task"], claims["worker"],
                        claims["lease_generation"], claims["job"],
                        claims["approval"], "started"))
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise PermissionError("Grant replay denied") from exc
        db.commit()
    finally:
        db.close()
    return claims


def finish_fenced_grant(ledger, grant_id, *, verified):
    """Never report completed unless the unit has been stop-verified."""
    if type(verified) is not bool:
        raise TypeError("Verified flag required")
    verify_private_ledger(ledger)
    with sqlite3.connect(ledger, timeout=5) as db:
        row = db.execute(
            "UPDATE signed_grant_consumptions SET status=? "
            "WHERE grant_id=? AND status='started'",
            ("completed" if verified else "failed", grant_id))
        if row.rowcount != 1:
            raise PermissionError("Grant not in started state")
