"""Read-only production cutover readiness inventory; never starts/stops units."""
import argparse
import os
import pwd
import stat
import subprocess

from .fenced_candidate_preflight import check


def inspect():
    check()
    for name in ("hermes-agency.service", "hermes-signed-broker.service"):
        result = subprocess.run(
            ["/usr/bin/systemctl", "show", name, "-p", "ActiveState",
             "-p", "ExecStart", "-p", "FragmentPath"],
            capture_output=True, text=True, timeout=10, check=False)
        if result.returncode:
            raise PermissionError("Production unit inventory unavailable: " + name)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines()
                      if "=" in line)
        if values.get("ActiveState") != "active":
            raise PermissionError("Production unit not active: " + name)
        expected = ("agency.single_vps_service" if name == "hermes-agency.service"
                    else "agency.supervised_broker")
        if expected not in values.get("ExecStart", ""):
            raise PermissionError("Unexpected production entrypoint: " + name)
        print("PRODUCTION_ENTRYPOINT_CONFIRMED=" + name, flush=True)
    paths = (
        ("/opt/hermes-agency", "candidate working directory"),
        ("/run/hermes-broker", "candidate socket directory"),
        ("/var/lib/hermes-broker", "candidate journal directory"),
        ("/var/lib/hermes-agency/agency.db", "trusted database"),
        ("/etc/hermes-broker/signing.key", "candidate signing key"),
    )
    for path, description in paths:
        if not os.path.exists(path):
            print("CUTOVER_PREREQUISITE_MISSING=" + description, flush=True)
        else:
            print("CUTOVER_PREREQUISITE_PRESENT=" + description, flush=True)
    try:
        user = pwd.getpwnam("hermes-trusted")
        db = os.stat("/var/lib/hermes-agency/agency.db")
        if db.st_uid != user.pw_uid or not stat.S_ISREG(db.st_mode):
            print("TRUSTED_DB_IDENTITY_CHECK=REVIEW", flush=True)
        else:
            print("TRUSTED_DB_IDENTITY_CHECK=PASS", flush=True)
    except (KeyError, OSError):
        print("TRUSTED_DB_IDENTITY_CHECK=REVIEW", flush=True)
    print("PRODUCTION_CUTOVER_EXECUTED=NO", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    inspect()


if __name__ == "__main__":
    main()
