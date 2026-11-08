"""Passive kernel flock observation correlated to the running operator sidecar.

No requests, locks, service changes, or production state mutations. A missing
sample is inconclusive. Observations never authorize cutover.
"""
import argparse
import json
import os
import time

from .production_runtime_evidence import capture


def matching_locks(lines, pid, device, inode):
    expected = (os.major(device), os.minor(device), inode)
    matches = []
    for line in lines:
        fields = line.split()
        if len(fields) < 6 or fields[1:3] != ["FLOCK", "ADVISORY"]:
            continue
        try:
            lock_pid = int(fields[4])
            major_hex, minor_hex, inode_dec = fields[5].split(":")
            major, minor, number = (int(major_hex, 16), int(minor_hex, 16),
                                    int(inode_dec, 10))
        except (ValueError, IndexError):
            continue
        if lock_pid == pid and (major, minor, number) == expected:
            matches.append({"mode": fields[3], "pid": lock_pid})
    return matches


def observe(duration=2.0, interval=0.02, reader=None, runtime=None, clock=None, sleeper=None):
    if not (0 < duration <= 10 and 0.005 <= interval <= 1):
        raise ValueError("Invalid bounded observation interval")
    reader = reader or (lambda: open("/proc/locks", encoding="ascii").read().splitlines())
    runtime = runtime or capture
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep
    before = runtime()
    deadline = clock() + duration
    samples = 0
    seen = []
    while True:
        seen.extend(matching_locks(reader(), before["sidecar_pid"],
                                   before["lock_device"], before["lock_inode"]))
        samples += 1
        if clock() >= deadline:
            break
        sleeper(interval)
    after = runtime()
    for key in ("sidecar_pid", "lock_device", "lock_inode", "snapshot"):
        if before[key] != after[key]:
            raise PermissionError("Runtime identity changed during observation")
    if not after["freeze_present"]:
        raise PermissionError("Freeze missing after observation")
    return {"kernel_flock_observed": bool(seen),
            "observed_modes": sorted(set(x["mode"] for x in seen)),
            "samples": samples,
            "sidecar_pid": before["sidecar_pid"],
            "lock_inode": before["lock_inode"],
            "live_admission_lock_participation": (
                "OBSERVED_SHARED_LOCK_NOT_AUTHORIZED" if any(
                    x["mode"] == "READ" for x in seen) else "NOT_ATTESTED"),
            "production_mutated_by_probe": False,
            "cutover_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--passive", action="store_true", required=True)
    parser.add_argument("--seconds", type=float, default=2.0)
    args = parser.parse_args(argv)
    try:
        result = observe(duration=args.seconds)
    except (OSError, ValueError, PermissionError) as exc:
        print("KERNEL_OBSERVATION=INCONCLUSIVE")
        print("ERROR=" + type(exc).__name__)
        print("PRODUCTION_CUTOVER_GO=NO")
        return 2
    print(json.dumps(result, sort_keys=True))
    print("KERNEL_OBSERVATION=OBSERVED" if result["kernel_flock_observed"]
          else "KERNEL_OBSERVATION=INCONCLUSIVE")
    print("PRODUCTION_CUTOVER_GO=NO")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
