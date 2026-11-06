#!/usr/bin/env python3
"""Operator-run live cross-UID positive workflow smoke test.

Root orchestrates separate hermes-trusted and hermes-worker processes.
Only hermes-trusted opens the signing key and SQLite database. Root relays
a short-lived *worker credential* over stdin; no credential is logged or
passed in argv/environment. No tool execution or systemd restart.
"""
import json
import os
import subprocess
import sys
import time

DB = "/var/lib/hermes-agency/agency.db"
KEY = "/var/lib/hermes-agency/keys/signing.key"
SOCKET = "/run/hermes-agency/trusted.sock"
RESULT = {"completed": ["live integration smoke"], "output": [], "notes": [], "blockers": []}


def trusted(mode, task=None):
    from agency.security import SecureAgencyStore
    from agency.orchestrator import WorkflowCoordinator
    from agency.trusted import TrustedApprovalService
    if os.geteuid() == 0:
        raise PermissionError("Trusted operation must be non-root")
    store = SecureAgencyStore(DB)
    try:
        workflow = WorkflowCoordinator(store)
        if mode == "issue":
            # Secret never leaves trusted process. Service owns the same key.
            with open(KEY, "rb") as handle:
                secret = handle.read(65)
            if len(secret) != 64:
                raise ValueError("Unexpected signing key length")
            issuer = TrustedApprovalService(store, secret)
            task_id = workflow.start("Cross-UID trusted socket integration smoke")
            credential = issuer.issue_credential("ceo", "worker", ttl=120)
            print(json.dumps({"task": task_id, "credential": credential}))
        elif mode == "verify":
            state = workflow.snapshot(task)
            handoffs = store.db.execute(
                "SELECT COUNT(*) FROM handoffs WHERE task_id=?", (task,)
            ).fetchone()[0]
            if state["stage"] != 1 or state["owner"] != "pm" or handoffs != 1:
                raise AssertionError("Workflow was not advanced exactly once")
            print("SQLITE_WORKFLOW_ADVANCED=PASS")
        else:
            raise ValueError("Unknown trusted mode")
    finally:
        store.close()


def worker():
    from agency.trusted_client import send_stage_confirmed
    if os.geteuid() == 0:
        raise PermissionError("Worker must be non-root")
    data = json.loads(sys.stdin.read(12000))
    for attempt in range(20):
        try:
            if send_stage_confirmed(
                SOCKET, data["task"], "ceo", RESULT, data["credential"], timeout=3
            ) is True:
                print("CROSS_UID_VALID_CREDENTIAL=PASS")
                return
        except (FileNotFoundError, ConnectionRefusedError):
            if attempt == 19:
                raise
            time.sleep(0.1)
    raise AssertionError("Socket unavailable")


def run_as(account, mode, input_text=None, task=None):
    args = ["runuser", "-u", account, "--", sys.executable, os.path.abspath(__file__), mode]
    if task is not None:
        args.append(task)
    env = os.environ.copy()
    env["PYTHONPATH"] = "/opt/hermes-agency"
    result = subprocess.run(
        args, input=input_text, text=True, capture_output=True,
        timeout=25, env=env, check=False
    )
    if result.returncode:
        # Do not echo stdout: issuer stdout may contain a credential.
        raise RuntimeError(mode + " failed: " + result.stderr[-1500:])
    return result.stdout


def main():
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "worker":
            return worker()
        if mode in ("issue", "verify"):
            return trusted(mode, sys.argv[2] if len(sys.argv) > 2 else None)
        raise ValueError("Unknown mode")
    if os.geteuid() != 0:
        raise PermissionError("Operator orchestration requires root")
    if not os.path.isfile("/opt/hermes-agency/agency/trusted.py"):
        raise RuntimeError("Deployed trusted runtime missing")
    issued = json.loads(run_as("hermes-trusted", "issue"))
    task = issued["task"]
    # Worker receives only a short-lived capability; never the signing key.
    output = run_as("hermes-worker", "worker", json.dumps(issued))
    if "CROSS_UID_VALID_CREDENTIAL=PASS" not in output:
        raise AssertionError("Missing worker acknowledgement")
    print("CROSS_UID_VALID_CREDENTIAL=PASS")
    print(run_as("hermes-trusted", "verify", task=task).strip())
    print("LIVE_E2E=PASS")


if __name__ == "__main__":
    main()
