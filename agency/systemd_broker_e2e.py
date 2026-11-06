"""Opt-in root operator end-to-end diagnostic: socket -> ledger -> systemd.

Never starts or changes the production trusted service. The test uses a
root-only temporary directory and a synthetic operator approval; it does NOT
claim trusted-service approval provenance or production readiness.
"""
import json
import os
import secrets
import socket
import sqlite3
import tempfile
import threading

from .systemd_broker import (initialize_ledger, provision_approval,
                             handle_connection, verify_private_ledger)


def run_operator_e2e():
    if os.geteuid() != 0:
        raise PermissionError("Operator root required")
    with tempfile.TemporaryDirectory(prefix="hermes-broker-e2e-") as directory:
        os.chmod(directory, 0o700)
        ledger = os.path.join(directory, "ledger.sqlite")
        initialize_ledger(ledger)
        verify_private_ledger(ledger)
        token = secrets.token_hex(32)
        provision_approval(ledger, token, "noop")
        server, client = socket.socketpair(socket.AF_UNIX)
        outcome = {}
        def worker():
            try:
                with server:
                    outcome["execution"] = handle_connection(server, os.geteuid(), ledger)
            except Exception as exc:
                outcome["error"] = exc
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            with client:
                client.settimeout(20)
                client.sendall((json.dumps({"job": "noop", "approval_id": token}) + "\n").encode())
                response = client.recv(4096)
        finally:
            thread.join(timeout=25)
        if thread.is_alive():
            raise RuntimeError("Broker integration thread timed out")
        if "error" in outcome:
            raise RuntimeError("Broker integration execution failed") from outcome["error"]
        result = json.loads(response)
        if result.get("isolated_backend") != "systemd" or result.get("exit_code") != 0:
            raise AssertionError("Real systemd execution not confirmed")
        with sqlite3.connect(ledger) as db:
            approval = db.execute("SELECT consumed FROM approvals WHERE id=?", (token,)).fetchone()
            statuses = [row[0] for row in db.execute("SELECT status FROM audit ORDER BY id")]
        if approval != (1,) or statuses != ["started", "completed"]:
            raise AssertionError("Approval consumption or audit incomplete")
        return {"operator_socket_to_systemd": "PASS",
                "one_time_approval": "PASS", "persistent_audit": "PASS",
                "trusted_service_integration": "NOT_TESTED",
                "production_enabled": False}


if __name__ == "__main__":
    print(json.dumps(run_operator_e2e(), indent=2))
