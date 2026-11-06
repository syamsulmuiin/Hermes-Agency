"""Strict JSON request validation for a future trusted process boundary.

No listener is started here. Authentication must happen in the trusted server
before these requests are passed to TrustedAgentExecution.
"""
import json

MAX_REQUEST_BYTES = 65536
_ALLOWED = frozenset({"task_id", "agent", "result", "worker_credential"})


def parse_stage_request(raw):
    """Parse an untrusted stage request without executing or authorizing it."""
    if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Invalid request size or type")
    try:
        request = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid JSON request") from exc
    if not isinstance(request, dict) or set(request) != _ALLOWED:
        raise ValueError("Invalid request fields")
    for field in ("task_id", "agent", "worker_credential"):
        value = request[field]
        if not isinstance(value, str) or not value or len(value) > 8192:
            raise ValueError("Invalid request identity or credential")
    if len(request["task_id"]) > 128 or len(request["agent"]) > 128:
        raise ValueError("Invalid task or agent identifier")
    result = request["result"]
    if not isinstance(result, dict) or set(result) != {
        "completed", "output", "notes", "blockers"
    }:
        raise ValueError("Invalid stage result")
    if not all(
        isinstance(v, list) and len(v) <= 100
        and all(isinstance(x, str) and len(x) <= 4096 for x in v)
        for v in result.values()
    ):
        raise ValueError("Invalid stage content")
    return request
