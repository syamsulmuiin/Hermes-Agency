"""Read-only inspection of installed independent PID1 recovery wiring.

Static wiring is not proof that recovery succeeds under SIGKILL. Never starts,
stops, reloads or enables a service and never authorizes production cutover.
"""
import argparse
import subprocess
import sys

BROKER = "hermes-fenced-broker-candidate.service"
RECOVERY = "hermes-fenced-recovery-candidate.service"
SNAPSHOT = "/opt/hermes-fenced-9bf261261b59"


def _show(unit):
    keys = ("LoadState", "WorkingDirectory", "User", "ExecStart",
            "ExecStartPre", "ExecStopPost", "OnFailure", "Requires", "After")
    result = subprocess.run(["/usr/bin/systemctl", "show", unit,
                             *("--property=" + key for key in keys)],
                            capture_output=True, text=True, timeout=10,
                            check=True)
    return dict(line.split("=", 1) for line in result.stdout.splitlines()
                if "=" in line)


def inspect():
    broker, recovery = _show(BROKER), _show(RECOVERY)
    for item in (broker, recovery):
        if (item.get("LoadState") != "loaded"
                or item.get("WorkingDirectory") != SNAPSHOT
                or item.get("User") != "root"):
            raise PermissionError("Candidate recovery identity mismatch")
    if (RECOVERY not in broker.get("OnFailure", "")
            or RECOVERY not in broker.get("Requires", "")
            or RECOVERY not in broker.get("After", "")
            or "fenced_startup_gate" not in broker.get("ExecStartPre", "")
            or "fenced_owned_recovery" not in broker.get("ExecStopPost", "")
            or "fenced_owned_recovery" not in recovery.get("ExecStart", "")):
        raise PermissionError("Independent PID1 recovery wiring incomplete")
    return {"installed_recovery_wiring": "PASS",
            "pid1_behavior": "NOT_ATTESTED",
            "cutover_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        report = inspect()
    except (OSError, ValueError, PermissionError, subprocess.SubprocessError) as exc:
        print("RECOVERY_WIRING=NO_GO")
        print("RECOVERY_ERROR=" + type(exc).__name__)
        print("PRODUCTION_MUTATED=NO")
        return 2
    for key, value in report.items():
        print(key.upper() + "=" + str(value))
    print("PRODUCTION_MUTATED=NO")
    return 2


if __name__ == "__main__":
    sys.exit(main())
