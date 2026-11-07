"""Static deployment preflight for the inactive fenced broker candidate.

Does not start services, create units or modify the production checkout.
Static validation is necessary but NOT proof of crash-safe deployment.
"""
import argparse
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "systemd"


def _unit(name):
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.optionxform = str
    with (DEPLOY / name).open(encoding="utf-8") as stream:
        config.read_file(stream)
    return config


def check():
    broker = _unit("hermes-fenced-broker-candidate.service")
    recovery = _unit("hermes-fenced-recovery-candidate.service")
    start = broker["Service"]["ExecStart"]
    pre = broker["Service"]["ExecStartPre"]
    rec = recovery["Service"]["ExecStart"]
    post = broker["Service"].get("ExecStopPost", "")
    expected_journal = "/var/lib/hermes-broker/owned-units.sqlite"
    if ("agency.fenced_broker_candidate" not in start
            or "--execute" not in start
            or "--journal " + expected_journal not in start
            or "--socket /run/hermes-broker/fenced-candidate.sock" not in start
            or "agency.fenced_startup_gate" not in pre
            or "--journal " + expected_journal not in pre):
        raise PermissionError("Candidate broker missing fenced execution or gate")
    if ("agency.fenced_owned_recovery" not in post
            or "--journal " + expected_journal not in post
            or "--execute" not in post):
        raise PermissionError("Candidate missing PID1 post-stop recovery")
    if ("agency.fenced_owned_recovery" not in rec
            or "--journal " + expected_journal not in rec
            or "--execute" not in rec):
        raise PermissionError("Candidate independent recovery missing")
    if (broker["Unit"].get("OnFailure") !=
            "hermes-fenced-recovery-candidate.service"):
        raise PermissionError("Broker failure does not trigger recovery")
    if broker["Service"].get("Restart") != "no":
        raise PermissionError("Candidate broker must not restart before recovery")
    if broker["Service"].get("User") != "root":
        raise PermissionError("Candidate root broker identity invalid")
    if recovery["Service"].get("User") != "root":
        raise PermissionError("Recovery root identity invalid")
    if "hermes-signed-broker.service" in start:
        raise PermissionError("Candidate must not replace production broker")
    print("FENCED_CANDIDATE_STATIC_PREFLIGHT=PASS")
    print("FENCED_CANDIDATE_RUNTIME_CRASH_VERIFIED=NO")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    check()


if __name__ == "__main__":
    main()
