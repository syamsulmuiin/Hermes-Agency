"""Signed, short-lived broker grants issued only after real trusted approval.

Broker verification is cryptographic; execution remains a separate operator
deployment step. The broker must keep its verification key root-owned.
"""
import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import time

from .security import fingerprint
from .systemd_jobs import JOBS


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def issue_broker_grant(service, approval, task_id, job, worker_credential,
                       lease_token, key, ttl=30):
    """Reserve an actual approved grant, then sign its bounded job identity."""
    if type(job) is not str or job not in JOBS:
        raise PermissionError("Job not allowlisted")
    if not isinstance(key, bytes) or len(key) < 32:
        raise PermissionError("Dedicated broker signing key required")
    if type(ttl) not in (int, float) or not 1 <= ttl <= 60:
        raise ValueError("Invalid grant lifetime")
    worker = service._verify(worker_credential, "worker")
    params = {"job": job}
    identifier = secrets.token_hex(32)
    result = service.grant(approval, task_id, "execute_shell", params,
                           worker_credential, lease_token, identifier)
    issued = service.clock()
    payload = {"v": 1, "aud": "hermes-systemd-broker-v1", "id": identifier,
               "approval": approval, "task": task_id, "worker": worker,
               "lease_generation": result["lease_generation"],
               "job": job, "params_hash": fingerprint(params),
               "iat": issued, "exp": min(issued + ttl, issued + 60)}
    raw = _canonical(payload)
    return {"claims": payload, "signature": hmac.new(key, raw, hashlib.sha256).hexdigest()}


def verify_broker_grant(envelope, key, now=None):
    if not isinstance(key, bytes) or len(key) < 32:
        raise PermissionError("Broker verification key required")
    if not isinstance(envelope, dict) or set(envelope) != {"claims", "signature"}:
        raise PermissionError("Invalid grant envelope")
    claims, signature = envelope["claims"], envelope["signature"]
    expected = {"v", "aud", "id", "approval", "task", "worker",
                "lease_generation", "job", "params_hash", "iat", "exp"}
    if not isinstance(claims, dict) or set(claims) != expected:
        raise PermissionError("Invalid grant claims")
    if type(signature) is not str or len(signature) != 64:
        raise PermissionError("Invalid grant signature")
    try:
        raw = _canonical(claims)
    except (ValueError, TypeError) as exc:
        raise PermissionError("Invalid grant encoding") from exc
    if len(raw) > 2048 or not hmac.compare_digest(hmac.new(key, raw, hashlib.sha256).hexdigest(), signature):
        raise PermissionError("Invalid grant signature")
    if claims["v"] != 1 or claims["aud"] != "hermes-systemd-broker-v1":
        raise PermissionError("Wrong grant audience")
    for field in ("id", "approval", "task", "worker"):
        if type(claims[field]) is not str or not 1 <= len(claims[field]) <= 128:
            raise PermissionError("Invalid grant identity")
    if type(claims["id"]) is not str or len(claims["id"]) != 64 or any(c not in "0123456789abcdef" for c in claims["id"]):
        raise PermissionError("Invalid grant identifier")
    if type(claims["lease_generation"]) is not int or claims["lease_generation"] < 1:
        raise PermissionError("Invalid lease generation")
    if type(claims["job"]) is not str or claims["job"] not in JOBS:
        raise PermissionError("Job not allowlisted")
    if claims["params_hash"] != fingerprint({"job": claims["job"]}):
        raise PermissionError("Job parameters mismatch")
    issued, expiry = claims["iat"], claims["exp"]
    current = time.time() if now is None else now
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in (issued, expiry, current)):
        raise PermissionError("Invalid grant clock")
    if not issued <= current < expiry or not 0 < expiry - issued <= 60:
        raise PermissionError("Expired or future grant")
    return claims


def verify_live_lease(trusted_db_path, claims, now=None):
    """Read-only live fencing check against trusted SQLite state.

    The trusted database must be opened through an operator-controlled path,
    never supplied by an untrusted socket request.
    """
    current = time.time() if now is None else now
    if not isinstance(trusted_db_path, str) or not trusted_db_path.startswith("/"):
        raise PermissionError("Trusted database path must be absolute")
    try:
        db = sqlite3.connect("file:" + trusted_db_path + "?mode=ro", uri=True, timeout=5)
        try:
            db.execute("PRAGMA query_only=ON")
            row = db.execute("""SELECT l.worker,l.generation,l.expires_at,t.status,t.owner
                FROM task_leases l JOIN tasks t ON t.id=l.task_id
                WHERE l.task_id=?""", (claims["task"],)).fetchone()
            grant = db.execute("""SELECT g.approval_id,g.worker,g.lease_generation,
                    g.action,g.params_hash,a.status
                FROM execution_grants g JOIN approvals a ON a.id=g.approval_id
                WHERE g.idempotency_key=? AND g.task_id=?""",
                (claims["id"], claims["task"])).fetchone()
        finally:
            db.close()
    except sqlite3.Error as exc:
        raise PermissionError("Trusted state unavailable") from exc
    if (not row or row[0] != claims["worker"]
        or row[1] != claims["lease_generation"] or row[2] <= current
        or row[3] != "in_progress" or row[4] not in ("developer", "qa", "researcher", "designer", "pm", "ceo")
        or not grant or grant != (claims["approval"], claims["worker"],
            claims["lease_generation"], "execute_shell", claims["params_hash"], "consumed")):
        raise PermissionError("Lease revoked, expired or grant provenance invalid")
    return True
