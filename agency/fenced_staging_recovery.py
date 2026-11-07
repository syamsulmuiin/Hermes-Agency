"""Independent root recovery entrypoint for isolated staging systemd units.

Designed to be invoked by an independently managed systemd recovery unit.
Never starts jobs and never touches the production service or trusted DB.
"""
import argparse
import os

from .fenced_staging_serialization import staging_recover
from .fenced_startup_gate import require_recovered


def recover_staging(journal):
    if os.geteuid() != 0:
        raise PermissionError("Root recovery required")
    recovered = staging_recover(journal)
    require_recovered(journal)
    return recovered


def main(argv=None):
    parser = argparse.ArgumentParser(description="Isolated staging journal recovery")
    parser.add_argument("--journal", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    recovered = recover_staging(args.journal)
    print("STAGING_RECOVERY_VERIFIED=" + str(len(recovered)), flush=True)


if __name__ == "__main__":
    main()
