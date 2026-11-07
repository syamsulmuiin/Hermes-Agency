"""Fail-closed journal startup gate for isolated broker test services.

Does not launch work, create grants, or touch production services.
The service manager must serialize recovery and broker startup externally.
"""
import argparse
import os
import sqlite3

from .fenced_unit_journal import _verify_store
from .fenced_systemd_supervisor import _unit_name


def require_recovered(journal):
    if os.geteuid() != 0 or not os.path.isfile(journal):
        raise PermissionError("Root and existing recovery journal required")
    _verify_store(journal)
    # Read-only: a startup gate must never silently perform recovery.
    with sqlite3.connect("file:" + journal + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT unit,state FROM owned_units").fetchall()
    for unit, state in rows:
        _unit_name(unit)
        if state not in ("pending", "verified"):
            raise PermissionError("Invalid journal state")
        if state == "pending":
            raise PermissionError("Recovery pending; broker startup denied")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True)
    args = parser.parse_args(argv)
    require_recovered(args.journal)
    print("journal_startup_gate=PASS", flush=True)


if __name__ == "__main__":
    main()
