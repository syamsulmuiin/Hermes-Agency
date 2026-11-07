"""Root-only opt-in acceptance for a supervised broker with a real trusted UID.

Requires an already running supervised broker pointed at the *isolated*
state, ledger and key paths supplied here. Never targets production state.
This module prepares an isolated signed grant through the trusted adapter.
"""
import argparse
import json
import os
import pwd
import sqlite3
import sys
from pathlib import Path

from .security import SecureAgencyStore
from .trusted import TrustedApprovalService
from .trusted_broker_adapter import execute_approved_job


def run_trusted_client(database, credential_key, broker_key, socket_path):
    if os.geteuid() == 0:
        raise PermissionError("Trusted client must be non-root")
    key = Path(credential_key).read_bytes()
    if len(key) != 64:
        raise PermissionError("Invalid isolated credential secret")
    store = SecureAgencyStore(database)
    try:
        service = TrustedApprovalService(store, key)
        task = store.create_task("Supervised broker integration acceptance", "developer")
        lease = store.claim(task, "worker", ttl=60)
        worker = service.issue_credential("worker", "worker")
        approval = store.request_approval(task, "execute_shell",
                                          {"job": "noop"}, "developer")
        approver = service.issue_credential("operator", "approver")
        service.decide(approval, approver, True)
        return execute_approved_job(service, approval, task, "noop", worker,
                                    lease, broker_key, socket_path)
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--credential-key", required=True)
    parser.add_argument("--broker-key", required=True)
    parser.add_argument("--socket", required=True)
    args = parser.parse_args()
    result = run_trusted_client(args.database, args.credential_key,
                                args.broker_key, args.socket)
    if result.get("isolated_backend") != "systemd" or result.get("exit_code") != 0:
        raise RuntimeError("Real systemd execution not confirmed")
    print(json.dumps({"supervised_trusted_adapter_to_systemd": "PASS",
                      "agent_tools_enabled": False}))


if __name__ == "__main__":
    main()
