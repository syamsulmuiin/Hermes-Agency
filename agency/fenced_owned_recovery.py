"""Root-owned recovery runner shared by staging and candidate production.

Never launches work. Recovery takes the same exclusive journal lock used by
fenced launches, then verifies that no pending unit remains.
"""
import argparse
import os

from .fenced_staging_serialization import staging_recover
from .fenced_startup_gate import require_recovered


def recover_owned_journal(journal):
    if os.geteuid() != 0:
        raise PermissionError("Root recovery required")
    recovered = staging_recover(journal)
    require_recovered(journal)
    return recovered


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    units = recover_owned_journal(args.journal)
    print("OWNED_UNIT_RECOVERY_VERIFIED=" + str(len(units)), flush=True)


if __name__ == "__main__":
    main()
