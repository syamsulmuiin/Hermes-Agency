#!/usr/bin/env python3
"""Non-destructive live negative-auth smoke test, run as hermes-worker.

No trusted key, task creation, database mutation or agent tool execution.
An unknown task with a deliberately invalid credential must be denied.
"""
import json
import os
import socket
import sys
import time

SOCKET = "/run/hermes-agency/trusted.sock"
REQUEST = {
    "task_id": "00000000-0000-0000-0000-000000000000",
    "agent": "ceo",
    "result": {"completed": [], "output": [], "notes": [], "blockers": []},
    "worker_credential": "invalid.smoke-test",
}

def main():
    if os.geteuid() == 0:
        raise SystemExit("FAIL: do not run the client as root")
    payload = json.dumps(REQUEST, separators=(",", ":")).encode()
    for attempt in range(20):
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(3)
                client.connect(SOCKET)
                client.sendall(payload)
                client.shutdown(socket.SHUT_WR)
                data = bytearray()
                while len(data) <= 128 and b"\n" not in data:
                    chunk = client.recv(128 - len(data) + 1)
                    if not chunk:
                        break
                    data.extend(chunk)
                if bytes(data) != b'{"status": "denied"}\n':
                    raise SystemExit("FAIL: unexpected acknowledgement (no secret printed)")
                print("INVALID_CREDENTIAL_DENIED=PASS")
                return
        except (FileNotFoundError, ConnectionRefusedError):
            if attempt == 19:
                raise
            time.sleep(0.1)
    raise SystemExit("FAIL: no listener")

if __name__ == "__main__":
    main()
