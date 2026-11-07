"""Read-only systemd sandbox access audit for the pinned fenced candidate.

Never starts a broker, signs grants, writes journals or changes production units.
"""
import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess

from .fenced_systemd_supervisor import stop_and_verify_unit

CANDIDATE = re.compile(r"^/opt/hermes-fenced-[0-9a-f]{12}$")
READ_PATHS = (
    "/var/lib/hermes-agency/agency.db",
    "/var/lib/hermes-broker/ledger.sqlite",
    "/etc/hermes-broker/signing.key",
)
DIRECTORIES = ("/run/hermes-broker", "/var/lib/hermes-broker")


def audit(deployed):
    if os.geteuid() != 0 or not Path("/run/systemd/system").is_dir():
        raise PermissionError("Root/systemd required")
    deployed = str(Path(deployed).resolve(strict=True))
    if not CANDIDATE.fullmatch(deployed):
        raise PermissionError("Pinned /opt candidate path required")
    if not Path(deployed, "agency/fenced_broker_candidate.py").is_file():
        raise PermissionError("Candidate modules absent")
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    # No file content is read, particularly not the private signing key.
    probe = (
        "import os,stat,sys; "
        "paths=sys.argv[1:]; "
        "[(lambda s,p: (print('RESOURCE_PRESENT='+p), "
        "None if stat.S_ISREG(s.st_mode) else (_ for _ in ()).throw("
        "PermissionError('not regular: '+p))))(os.stat(p),p) for p in paths[:3]]; "
        "[(lambda s,p: (print('RESOURCE_DIRECTORY='+p), "
        "None if stat.S_ISDIR(s.st_mode) else (_ for _ in ()).throw("
        "PermissionError('not directory: '+p))))(os.stat(p),p) for p in paths[3:]]; "
        "print('CANDIDATE_RESOURCE_METADATA=PASS')"
    )
    command = [
        "/usr/bin/systemd-run", "--system", "--wait", "--collect", "--pipe",
        "--unit=" + unit, "--property=Type=exec",
        "--property=User=root", "--property=Group=root",
        "--property=WorkingDirectory=" + deployed,
        "--property=NoNewPrivileges=yes", "--property=ProtectSystem=strict",
        "--property=ReadWritePaths=/run/hermes-broker /var/lib/hermes-broker",
        "--property=ProtectHome=yes", "--property=PrivateTmp=yes",
        "--", "/usr/bin/python3", "-c", probe, *READ_PATHS, *DIRECTORIES,
    ]
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=40)
        if result.returncode or "CANDIDATE_RESOURCE_METADATA=PASS" not in result.stdout:
            raise RuntimeError("Sandbox resource metadata audit failed: "
                               + result.stderr[-1200:])
        print(result.stdout, end="")
        print("RESOURCE_CONTENT_OR_WRITE_TESTED=NO")
        print("PRODUCTION_CUTOVER_EXECUTED=NO")
    finally:
        stop_and_verify_unit(unit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--deployed", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    audit(args.deployed)


if __name__ == "__main__":
    main()
