"""Read-only production SQLite state compatibility audit and copy-only rehearsal.

No production service changes. No SQL writes to source databases.
Reports counts/schema only, never grant IDs or secrets.
"""
import argparse
import os
from pathlib import Path
import sqlite3
import tempfile

LEDGER = "/var/lib/hermes-broker/ledger.sqlite"
JOURNAL = "/var/lib/hermes-broker/owned-units.sqlite"
TRUSTED = "/var/lib/hermes-agency/agency.db"
SIGNED = {"grant_id", "task_id", "worker", "lease_generation", "job", "approval_id", "status"}
OWNED = {"unit", "state"}


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def source(path):
    if not Path(path).is_file() or Path(path).is_symlink():
        raise RuntimeError("Missing or unsafe source: " + path)
    return sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=3)


def snapshot(path, dest):
    with source(path) as src, sqlite3.connect(dest) as dst:
        src.backup(dst, pages=64, sleep=0.05)
        result = dst.execute("PRAGMA quick_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError("Backup integrity check failed")
    return True


def tables(db):
    return {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def columns(db, table):
    return {row[1] for row in db.execute("PRAGMA table_info(" + quoted(table) + ")")}


def count(db, table, predicate=None):
    sql = "SELECT COUNT(*) FROM " + quoted(table)
    if predicate:
        sql += " WHERE " + predicate
    return db.execute(sql).fetchone()[0]


def report(ledger, journal, trusted):
    with sqlite3.connect(ledger) as l, sqlite3.connect(journal) as j, sqlite3.connect(trusted) as t:
        lt, jt, tt = tables(l), tables(j), tables(t)
        print("LEDGER_TABLES=" + ",".join(sorted(lt)))
        print("TRUSTED_TABLE_COUNT=" + str(len(tt)))
        print("LEDGER_SIGNED_GRANT_TABLE=" + ("PRESENT" if "signed_grant_consumptions" in lt else "ABSENT"))
        if "signed_grant_consumptions" in lt:
            cols = columns(l, "signed_grant_consumptions")
            print("SIGNED_GRANT_SCHEMA=" + ("COMPATIBLE" if SIGNED <= cols else "INCOMPATIBLE"))
            print("SIGNED_GRANT_CONSUMPTIONS=" + str(count(l, "signed_grant_consumptions")))
            for state in ("started", "completed", "failed"):
                print("SIGNED_GRANT_" + state.upper() + "=" +
                      str(count(l, "signed_grant_consumptions", "status='" + state + "'")))
        else:
            print("SIGNED_GRANT_SCHEMA=ABSENT_LAZY_CREATION_EXPECTED")
        if "approvals" in lt:
            ac = columns(l, "approvals")
            if {"id", "job", "consumed"} <= ac:
                print("LEGACY_APPROVALS_UNCONSUMED=" + str(count(l, "approvals", "consumed=0")))
                print("LEGACY_APPROVALS_CONSUMED=" + str(count(l, "approvals", "consumed<>0")))
            else:
                print("LEGACY_APPROVAL_SCHEMA=INCOMPATIBLE")
        print("OWNERSHIP_JOURNAL=" + ("PRESENT" if "owned_units" in jt else "MISSING"))
        if "owned_units" in jt:
            print("OWNERSHIP_SCHEMA=" + ("COMPATIBLE" if OWNED <= columns(j, "owned_units") else "INCOMPATIBLE"))
            print("OWNED_PENDING=" + str(count(j, "owned_units", "state='pending'")))
            print("OWNED_VERIFIED=" + str(count(j, "owned_units", "state='verified'")))
            print("OWNED_OTHER=" + str(count(j, "owned_units", "state NOT IN ('pending','verified') OR state IS NULL")))
        print("TRUSTED_DATABASE_QUICK_CHECK=" + str(t.execute("PRAGMA quick_check").fetchone()[0]))
        print("LEDGER_DATABASE_QUICK_CHECK=" + str(l.execute("PRAGMA quick_check").fetchone()[0]))
        print("JOURNAL_DATABASE_QUICK_CHECK=" + str(j.execute("PRAGMA quick_check").fetchone()[0]))


def simulate(ledger, journal, trusted):
    # Only copies are mutated. No systemctl, no network, no live jobs.
    with sqlite3.connect(ledger) as l, sqlite3.connect(journal) as j:
        if "owned_units" not in tables(j):
            print("COPY_REHEARSAL=BLOCKED_NO_JOURNAL")
            return
        if count(j, "owned_units", "state='pending'") != 0:
            print("COPY_REHEARSAL=BLOCKED_PENDING_UNITS")
            return
        if "signed_grant_consumptions" in tables(l):
            before = count(l, "signed_grant_consumptions")
            l.execute("SAVEPOINT rollback_rehearsal")
            # Exercise rollback without altering grant rows, preserving replay state.
            l.execute("CREATE TABLE rehearsal_marker(value INTEGER)")
            l.execute("INSERT INTO rehearsal_marker VALUES (1)")
            l.execute("ROLLBACK TO rollback_rehearsal")
            l.execute("RELEASE rollback_rehearsal")
            after = count(l, "signed_grant_consumptions")
            if before != after or "rehearsal_marker" in tables(l):
                raise RuntimeError("Ledger copy rollback invariant failed")
        j.execute("SAVEPOINT recovery_rehearsal")
        j.execute("INSERT INTO owned_units(unit,state) VALUES ('hermes-fenced-rehearsal-fixture.service','pending')")
        if count(j, "owned_units", "state='pending'") != 1:
            raise RuntimeError("Copy pending gate invariant failed")
        j.execute("UPDATE owned_units SET state='verified' WHERE unit='hermes-fenced-rehearsal-fixture.service'")
        if count(j, "owned_units", "state='pending'") != 0:
            raise RuntimeError("Copy recovery state invariant failed")
        j.execute("ROLLBACK TO recovery_rehearsal")
        j.execute("RELEASE recovery_rehearsal")
        print("COPY_PENDING_GATE_RECOVERY_ROLLBACK=PASS")
        print("COPY_LEDGER_REPLAY_HISTORY_PRESERVED=PASS")
        print("COPY_REHEARSAL=PASS")
        print("REAL_SYSTEMD_CUTOVER_TESTED=NO")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--journal", default=JOURNAL)
    parser.add_argument("--trusted", default=TRUSTED)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Root read permission required")
    with tempfile.TemporaryDirectory(prefix="hermes-state-audit-", dir="/run") as tmp:
        os.chmod(tmp, 0o700)
        paths = []
        for label, original in (("ledger", args.ledger), ("journal", args.journal), ("trusted", args.trusted)):
            if label == "journal" and not os.path.exists(original):
                dest = os.path.join(tmp, label + ".sqlite")
                with sqlite3.connect(dest):
                    pass
                print("OWNERSHIP_JOURNAL_SOURCE=ABSENT")
                paths.append(dest)
                continue
            dest = os.path.join(tmp, label + ".sqlite")
            snapshot(original, dest)
            print("SQLITE_ONLINE_BACKUP_" + label.upper() + "=PASS")
            paths.append(dest)
        report(*paths)
        simulate(*paths)


if __name__ == "__main__":
    main()
