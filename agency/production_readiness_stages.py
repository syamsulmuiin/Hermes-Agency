"""Read-only stage-1 runtime evidence and stage-2 deployment prerequisites.

Never changes production state. A report is not cutover authorization.
"""
import argparse
import os
import pathlib
import stat
import subprocess
import sys

from .production_cutover_preflight import EXPECTED_PIN, SERVICES


def _show(unit, *properties):
    cmd = ["/usr/bin/systemctl", "show", unit]
    cmd.extend("--property=" + p for p in properties)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise PermissionError("systemctl show failed for " + unit)
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def _regular(path, mode, owner=0):
    try:
        info = os.lstat(path)
        return (stat.S_ISREG(info.st_mode) and info.st_uid == owner
                and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == mode)
    except OSError:
        return False


def audit():
    blockers = []
    evidence = []
    for unit in SERVICES:
        try:
            state = _show(unit, "ActiveState", "MainPID", "ExecStart", "FragmentPath", "User", "Group")
            pid = int(state.get("MainPID", "0"))
            if state.get("ActiveState") != "active" or pid <= 0:
                blockers.append(unit + ": no active main process")
                continue
            exe = os.readlink("/proc/%d/exe" % pid)
            cmdline = pathlib.Path("/proc/%d/cmdline" % pid).read_bytes().replace(bytes([0]), b" ").decode("utf-8", "replace")
            evidence.append(unit + " PID=" + str(pid) + " EXE=" + exe)
            evidence.append(unit + " CMDLINE=" + cmdline[:400])
            evidence.append(unit + " FRAGMENT=" + state.get("FragmentPath", ""))
        except (OSError, ValueError, PermissionError, subprocess.TimeoutExpired) as exc:
            blockers.append(unit + ": runtime identity not attested (" + type(exc).__name__ + ")")
    snapshot = pathlib.Path("/opt/hermes-fenced-" + EXPECTED_PIN)
    if not snapshot.is_dir() or snapshot.is_symlink():
        blockers.append("Pinned candidate snapshot missing or symlink")
    else:
        evidence.append("CANDIDATE_SNAPSHOT=" + str(snapshot))
        # Revalidate the complete pinned Git tree and deployment identity on
        # every audit. A prior manual PASS is not reusable authorization.
        try:
            from .fenced_snapshot_acceptance_preflight import audit as snapshot_audit
            if snapshot_audit(pathlib.Path("/root/Hermes-Agency")) == 0:
                evidence.append("CANDIDATE_CONTENT_MANIFEST=PASS")
            else:
                blockers.append("Candidate content digest and deployment manifest not attested")
        except (OSError, ValueError, PermissionError, subprocess.SubprocessError) as exc:
            blockers.append("Candidate content digest and deployment manifest not attested: "
                            + type(exc).__name__)
    lock = "/run/hermes-admission/admission.lock"
    if not _regular(lock, 0o640):
        blockers.append("Admission lock not securely provisioned")
    else:
        info = os.stat(lock)
        evidence.append("ADMISSION_LOCK_INODE=" + str(info.st_dev) + ":" + str(info.st_ino))
    journal = "/var/lib/hermes-broker/owned-units.sqlite"
    if not _regular(journal, 0o600):
        blockers.append("Ownership journal not securely provisioned")
    else:
        try:
            from .fenced_startup_gate import require_recovered
            require_recovered(journal)
            evidence.append("OWNERSHIP_RECOVERY_GATE=PASS")
        except (OSError, PermissionError, ValueError) as exc:
            blockers.append("Ownership recovery gate not attested: " + type(exc).__name__)
    # Installed systemd wiring is evidence; source templates alone are insufficient.
    for unit in ("hermes-fenced-broker-candidate.service",
                 "hermes-fenced-recovery-candidate.service"):
        try:
            state = _show(unit, "LoadState", "FragmentPath", "WorkingDirectory", "ExecStart",
                          "ExecStartPre", "ExecStopPost", "OnFailure")
            evidence.append(unit + " LOAD=" + state.get("LoadState", "unknown")
                            + " FRAGMENT=" + state.get("FragmentPath", ""))
            if state.get("WorkingDirectory") != str(snapshot):
                blockers.append(unit + ": installed working directory does not match accepted snapshot")
            if state.get("LoadState") != "loaded" or not state.get("FragmentPath"):
                blockers.append(unit + ": candidate systemd unit not installed")
            elif unit.endswith("broker-candidate.service"):
                if ("fenced_startup_gate" not in state.get("ExecStartPre", "")
                        or "fenced_owned_recovery" not in state.get("ExecStopPost", "")
                        or "hermes-fenced-recovery-candidate.service" not in state.get("OnFailure", "")):
                    blockers.append("Installed candidate broker recovery wiring incomplete")
            elif "fenced_owned_recovery" not in state.get("ExecStart", ""):
                blockers.append("Installed recovery unit lacks owned recovery entrypoint")
        except (OSError, PermissionError, subprocess.TimeoutExpired) as exc:
            blockers.append(unit + ": installed systemd wiring not verifiable (" + type(exc).__name__ + ")")
    # Runtime identity is observed independently; this is not behavioral
    # admission attestation and cannot authorize a production cutover.
    try:
        from .production_runtime_evidence import capture
        runtime = capture()
        evidence.append("SIDECAR_RUNTIME_IDENTITY=" + runtime["runtime_identity"])
        evidence.append("SIDECAR_RUNTIME_PID=" + str(runtime["sidecar_pid"]))
        evidence.append("SIDECAR_RUNTIME_SNAPSHOT=" + runtime["snapshot"])
        evidence.append("SIDECAR_ADMISSION_BEHAVIOR=" + runtime["admission_behavior"])
        if runtime["cutover_authorized"] is not False:
            blockers.append("Runtime evidence unexpectedly claims cutover authorization")
    except (OSError, ValueError, PermissionError, KeyError, subprocess.SubprocessError) as exc:
        blockers.append("Sidecar runtime identity not independently attested: " + type(exc).__name__)
    # Installed recovery wiring is observable; actual PID1 recovery behavior
    # remains a separate cutover blocker until independently attested.
    try:
        from .production_recovery_wiring_evidence import inspect
        recovery = inspect()
        if recovery["installed_recovery_wiring"] == "PASS" and recovery["cutover_authorized"] is False:
            evidence.append("INSTALLED_PID1_RECOVERY_WIRING=PASS")
            evidence.append("PID1_RECOVERY_BEHAVIOR=" + recovery["pid1_behavior"])
        else:
            blockers.append("Installed PID1 recovery wiring evidence invalid")
    except (OSError, ValueError, PermissionError, KeyError, subprocess.SubprocessError) as exc:
        blockers.append("Installed PID1 recovery wiring not verified: " + type(exc).__name__)
    # Distinguish locally observed state from external acceptance evidence.
    # Prior manual tests are not durable attestations; never auto-promote them.
    evidence.append("CANDIDATE_ROUTE_UNIT_TESTS=EXTERNAL_RESULT_NOT_ATTESTED")
    evidence.append("TMPFILES_EMPTY_DIRECTORY_TEST=EXTERNAL_RESULT_NOT_ATTESTED")
    evidence.append("LIVE_ADMISSION_FLOCK_TEST=EXTERNAL_RESULT_NOT_ATTESTED")
    evidence.append("PRODUCTION_BOOT_FROM_EMPTY_RUN=NOT_TESTED")
    # These are live behavioral properties; filesystem inspection cannot prove them.
    blockers.extend((
        "Live sidecar admission-lock participation not behaviorally attested",
        "Exclusive production drain and inode stability not behaviorally attested",
        "Production-route handover and rollback not acceptance-tested",
        "Independent PID1 recovery wiring for deployed candidate not attested",
        "Admission provisioning boot from empty /run not attested",
    ))
    for item in evidence:
        print("STAGE1_EVIDENCE=" + item)
    for item in blockers:
        print("STAGE1_BLOCKER=" + item)
    print("STAGE1_RESULT=" + ("PASS" if not blockers else "NO_GO"))
    print("PRODUCTION_MUTATED=NO")
    return 0 if not blockers else 2


def stage2_plan():
    print("STAGE2_MODE=PLAN_ONLY")
    print("STAGE2_PREREQUISITE=Independent verified snapshot manifest and matching runtime binaries")
    print("STAGE2_PREREQUISITE=Live sidecar admission-lock attestation and exclusive drain")
    print("STAGE2_PREREQUISITE=Authorized maintenance window and operator approval")
    print("STAGE2_SEQUENCE=Freeze admission; verify quiescence; stop both brokers; provision journal under drain")
    print("STAGE2_SEQUENCE=Verify persistent lock inode; install independent recovery; run startup gate")
    print("STAGE2_SEQUENCE=Start candidate; route with rollback retained; probe replay and health")
    print("STAGE2_SEQUENCE=On failure rollback route and broker without resetting replay ledger")
    print("STAGE2_SEQUENCE=Unfreeze only after verified recovery or successful handover")
    print("STAGE2_EXECUTION=DISABLED")
    print("PRODUCTION_MUTATED=NO")
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stage1-read-only", action="store_true")
    group.add_argument("--stage2-plan", action="store_true")
    args = parser.parse_args(argv)
    return audit() if args.stage1_read_only else stage2_plan()


if __name__ == "__main__":
    sys.exit(main())
