"""Read-only final fenced candidate systemd manifest gate.

Does not install, start, stop or change any systemd unit.
"""
import argparse
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROKER = ROOT / "deploy/systemd/hermes-fenced-broker-candidate.service"
RECOVERY = ROOT / "deploy/systemd/hermes-fenced-recovery-candidate.service"
PINNED = "/opt/hermes-fenced-377abe8b948b"

def read(path):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read(path)
    return parser

def audit():
    broker, recovery = read(BROKER), read(RECOVERY)
    problems = []
    def check(condition, name):
        if not condition:
            problems.append(name)
    b, r = broker["Service"], recovery["Service"]
    bu, ru = broker["Unit"], recovery["Unit"]
    check(b.get("WorkingDirectory") == PINNED, "broker pinned deployment path")
    check(r.get("WorkingDirectory") == PINNED, "recovery pinned deployment path")
    check(b.get("User") == "root" and r.get("User") == "root", "root ownership")
    check(b.get("ProtectSystem") == "strict" and r.get("ProtectSystem") == "strict", "strict filesystem sandbox")
    check(b.get("ProtectHome") == "yes" and r.get("ProtectHome") == "yes", "home protection")
    check(b.get("NoNewPrivileges") == "yes" and r.get("NoNewPrivileges") == "yes", "privilege restriction")
    check("hermes-fenced-recovery-candidate.service" in bu.get("Requires", "").split(), "recovery required")
    check("hermes-fenced-recovery-candidate.service" in bu.get("After", "").split(), "recovery ordering")
    check("hermes-fenced-recovery-candidate.service" in bu.get("OnFailure", "").split(), "failure recovery")
    check("fenced_startup_gate" in b.get("ExecStartPre", ""), "startup gate")
    check("fenced_owned_recovery" in b.get("ExecStopPost", ""), "stop recovery")
    check("fenced_owned_recovery" in r.get("ExecStart", ""), "independent recovery")
    check(b.get("Restart") == "no", "no automatic broker restart")
    check("/run/hermes-broker" in b.get("ReadWritePaths", "").split(), "socket writable")
    check("/var/lib/hermes-broker" in b.get("ReadWritePaths", "").split(), "journal writable")
    # The real trusted UID must be able to update its SQLite lease under the
    # effective sandbox. Static unit text alone cannot establish that.
    check("/var/lib/hermes-agency" in b.get("ReadWritePaths", "").split(),
          "trusted SQLite directory writable for WAL/lease")
    check(b.get("ExecStart", "").find("--socket /run/hermes-broker/fenced-candidate.sock") >= 0,
          "candidate-only socket")
    check("broker.sock" not in b.get("ExecStart", "").replace("fenced-candidate.sock", ""),
          "no legacy socket binding")
    for problem in problems:
        print("CUTOVER_BLOCKER=" + problem)
    print("FENCED_MANIFEST_STATIC_GATE=" + ("PASS" if not problems else "FAIL"))
    print("EFFECTIVE_SYSTEMD_RUNTIME_TESTED=NO")
    print("TRUSTED_OPERATOR_E2E_TESTED=NO")
    print("PRODUCTION_CUTOVER_EXECUTED=NO")
    return not problems

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    if not audit():
        raise SystemExit(2)

if __name__ == "__main__":
    main()
