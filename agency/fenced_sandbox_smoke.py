"""Isolated systemd sandbox smoke test against a pinned candidate checkout.

Uses a randomly named transient unit with candidate sandbox properties, but
does not start a broker, touch live journals, or change installed unit files.
"""
import argparse
import os
from pathlib import Path
import secrets
import subprocess

from .fenced_systemd_supervisor import stop_and_verify_unit


def run(deployed):
    if os.geteuid() != 0 or not Path("/run/systemd/system").is_dir():
        raise PermissionError("Root and systemd required")
    deployed = Path(deployed).resolve(strict=True)
    if not deployed.is_dir() or not (deployed / "agency/fenced_broker_candidate.py").is_file():
        raise PermissionError("Missing candidate deployment")
    if not str(deployed).startswith("/opt/hermes-fenced-"):
        raise PermissionError("Only versioned /opt candidate directories accepted")
    unit = "hermes-fenced-" + secrets.token_hex(16) + ".service"
    # Probe exact security directives without binding candidate socket or
    # opening live signing keys, ledgers or trusted databases.
    probe = ("import agency.fenced_broker_candidate, "
             "agency.fenced_owned_recovery, agency.fenced_systemd_supervisor; "
             "print('SANDBOX_IMPORTS=PASS')")
    cmd = [
        "/usr/bin/systemd-run", "--system", "--wait", "--collect", "--pipe",
        "--unit=" + unit,
        "--property=Type=exec",
        "--property=User=root",
        "--property=Group=root",
        "--property=WorkingDirectory=" + str(deployed),
        "--property=NoNewPrivileges=yes",
        "--property=ProtectSystem=strict",
        "--property=ReadWritePaths=/run/hermes-broker /var/lib/hermes-broker",
        "--property=ProtectHome=yes",
        "--property=PrivateTmp=yes",
        "--", "/usr/bin/python3", "-c", probe,
    ]
    try:
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=30,
                                check=False)
        if result.returncode or "SANDBOX_IMPORTS=PASS" not in result.stdout:
            raise RuntimeError("Candidate sandbox probe failed: "
                               + result.stderr[-1500:])
        print("CANDIDATE_ACTUAL_SANDBOX_IMPORTS=PASS", flush=True)
        print("PRODUCTION_CUTOVER_EXECUTED=NO", flush=True)
    finally:
        # Only the exact random transient probe unit; never a production unit.
        stop_and_verify_unit(unit)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--deployed", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Explicit --execute required")
    run(args.deployed)


if __name__ == "__main__":
    main()
