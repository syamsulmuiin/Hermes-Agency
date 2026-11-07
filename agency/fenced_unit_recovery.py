"""Independent, opt-in recovery for orphaned Hermes fenced transient units.

Run only from a dedicated root recovery service after broker shutdown/crash.
This module never launches jobs, issues grants or accesses the trusted DB.
"""
import os
import re
import subprocess

from .fenced_systemd_supervisor import _unit_name, stop_and_verify_unit

UNIT_PATTERN = re.compile(r"\Ahermes-fenced-[0-9a-f]{32}\.service\Z")


def discover_fenced_units(runner=subprocess.run):
    """Enumerate loaded units only; reject partial/ambiguous enumeration."""
    try:
        result = runner(
            ["/usr/bin/systemctl", "--system", "list-units",
             "--all", "--type=service", "--no-legend", "--no-pager",
             "--plain", "--full"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PermissionError("Recovery enumeration unavailable") from exc
    if result.returncode != 0 or len(result.stdout) > 1048576:
        raise PermissionError("Recovery enumeration failed")
    try:
        lines = result.stdout.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError as exc:
        raise PermissionError("Invalid systemd enumeration") from exc
    units = set()
    for line in lines:
        columns = line.split()
        if not columns:
            continue
        # list-units can prefix failed units with a bullet.
        if columns[0] == "●":
            columns = columns[1:]
        if not columns:
            raise PermissionError("Invalid systemd unit listing")
        name = columns[0]
        if name.startswith("hermes-fenced-"):
            _unit_name(name)
            units.add(name)
    return tuple(sorted(units))


def recover_fenced_units(*, broker_stopped, runner=subprocess.run,
                         stop_unit=stop_and_verify_unit):
    """Fail closed unless external orchestration has stopped the broker.

    broker_stopped must come from the dedicated service's systemd ordering,
    not from an untrusted IPC request. A new broker must not start until this
    recovery service exits successfully.
    """
    if os.geteuid() != 0 or broker_stopped is not True:
        raise PermissionError("Root-only recovery requires stopped broker")
    units = discover_fenced_units(runner=runner)
    failures = []
    for unit in units:
        try:
            stop_unit(unit)
        except (PermissionError, OSError):
            failures.append(unit)
    if failures:
        raise PermissionError("One or more fenced units remain unverified")
    return units


def main(argv=None):
    """CLI for an explicitly installed systemd broker lifecycle drop-in.

    Both ExecStartPre and ExecStopPost run outside the broker's main process.
    The drop-in is not installed by this module.
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker-stopped", action="store_true", required=True)
    args = parser.parse_args(argv)
    recovered = recover_fenced_units(broker_stopped=args.broker_stopped)
    print("fenced_unit_recovery_verified=" + str(len(recovered)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
