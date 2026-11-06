"""Unprivileged client transport for a trusted Unix stage submission.

This client cannot mint credentials, access the trusted database or execute
tools. Sending a request is NOT an acknowledgement that the server accepted it:
the current one-shot server intentionally has no response protocol.
"""
import json
import os
import socket

from .trusted_protocol import MAX_REQUEST_BYTES, parse_stage_request


def send_stage(path, task_id, agent, result, worker_credential, timeout=3):
    """Send a strictly validated stage request to an existing Unix socket."""
    if not isinstance(path, str) or not path or len(os.fsencode(path)) > 100:
        raise ValueError("Invalid socket path")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 10:
        raise ValueError("Invalid timeout")
    payload = json.dumps({
        "task_id": task_id,
        "agent": agent,
        "result": result,
        "worker_credential": worker_credential,
    }, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("Request exceeds size limit")
    parse_stage_request(payload)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(path)
        connection.sendall(payload)
        connection.shutdown(socket.SHUT_WR)
    return None


def send_stage_confirmed(path, task_id, agent, result, worker_credential, timeout=3):
    """Send a stage and require an explicit trusted-service acknowledgement.

    Use only with a server that implements agency.trusted_ack. This transport
    does not itself authenticate the server's OS identity.
    """
    from .trusted_ack import read_ack
    if not isinstance(path, str) or not path or len(os.fsencode(path)) > 100:
        raise ValueError("Invalid socket path")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 10:
        raise ValueError("Invalid timeout")
    payload = json.dumps({
        "task_id": task_id, "agent": agent, "result": result,
        "worker_credential": worker_credential,
    }, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("Request exceeds size limit")
    parse_stage_request(payload)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(path)
        connection.sendall(payload)
        connection.shutdown(socket.SHUT_WR)
        return read_ack(connection)
