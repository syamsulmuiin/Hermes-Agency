"""Interactive root-only operator client. Secrets never appear in argv or logs."""
import argparse
import getpass
import json
import os
import socket

from .operator_control import MAX_OPERATOR_REQUEST


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local authenticated Hermes operator")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--action", choices=("approve", "approve_and_execute"),
                        default="approve")
    parser.add_argument("--task-id")
    parser.add_argument("--job")
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.error("Root operator UID required; do not run as worker")
    if not os.path.isabs(args.socket):
        parser.error("Absolute operator socket path required")
    if args.action == "approve_and_execute":
        if not args.task_id or not args.job:
            parser.error("--task-id and --job required for approve_and_execute")
    elif args.task_id or args.job:
        parser.error("Execution arguments are only valid for approve_and_execute")

    operator_secret_hex = getpass.getpass("Operator secret (64 hex chars): ").strip()
    request = {
        "action": args.action,
        "approval_id": args.approval_id,
        "operator_secret_hex": operator_secret_hex,
    }
    if args.action == "approve_and_execute":
        request.update({
            "task_id": args.task_id,
            "job": args.job,
            "worker_credential": getpass.getpass("Verified worker credential: "),
            "lease_token": getpass.getpass("Active worker lease token: "),
        })
    # Validate before opening a connection. No secret is printed on failure.
    from .operator_control import parse_operator_request
    payload = json.dumps(request, separators=(",", ":")).encode("utf-8")
    try:
        parse_operator_request(payload)
    except PermissionError:
        parser.error("Invalid operator request fields")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(args.socket)
        connection.sendall(payload + b"\n")
        connection.shutdown(socket.SHUT_WR)
        response = bytearray()
        while len(response) <= 128:
            part = connection.recv(129 - len(response))
            if not part:
                break
            response.extend(part)
            if b"\n" in part:
                break
    if len(response) > 128 or not response.endswith(b"\n"):
        raise PermissionError("Missing or invalid operator response")
    try:
        result = json.loads(bytes(response[:-1]))
    except (ValueError, UnicodeError) as exc:
        raise PermissionError("Malformed operator response") from exc
    if result != {"status": "accepted"}:
        raise PermissionError("Operator request denied")
    print("operator_request=accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
