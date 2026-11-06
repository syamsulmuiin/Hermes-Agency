# Trusted Runtime Foundation — security boundaries

This is a **prototype authorization boundary**, not an executable agent runtime.

## Implemented
- Legacy `SecureAgencyStore.decide()`, `consume()`, and `decide_authenticated()` entrypoints reject calls.
- `TrustedApprovalService` verifies HMAC-SHA256 signed, expiring, audience-bound credentials with approver/worker roles.
- Only the trusted server may hold the signing key and issue credentials after real identity verification. **Do not expose `issue_credential()` to agents, tools, or unauthenticated API clients.**
- Reviewer cannot approve a request from the same agent identity; requests are single-use and parameter-bound.
- Execution grant reservation checks active task state, worker identity, fencing lease token, approval expiry and action digest in one SQLite transaction.
- Idempotency key and approval ID are unique in `execution_grants`; replay is rejected.
- Claims and handoffs use `BEGIN IMMEDIATE` for local SQLite serialization.

## Still unsafe for execution
- HMAC credentials are not a login mechanism. There is no network server, TLS identity provider, secret rotation, revocation list, or authorization middleware.
- Any code with direct database access or the signing key can bypass this in-process boundary. Protect the process and DB with OS permissions and a separate trusted service.
- `_decide_internal` and `_consume_internal` are private-by-convention only; Python does not enforce isolation.
- A reserved grant is **not** a capability to execute external commands. Tool-side fencing, sandbox, allowlists, timeout and side-effect idempotency must be implemented before wiring tools.
- There is no durable job scheduler, LLM adapter, self-repair, or deployment.
- GitHub Actions test results must be inspected; uploaded code alone does not prove test success.

## Test
`python -m unittest discover -s tests -v`

## Next gate
Trusted server authentication (OIDC/session or local authenticated approval UI), signed principal issuance inside the trusted process, key storage and rotation, tool-side idempotency, sandbox and crash-recovery tests.

## Phase 5G sandbox probe
- Fixed Bubblewrap /bin/true capability probe only; no agent-controlled command.
- Uses an empty environment, read-only system mounts, private /tmp, isolated namespaces, a timeout, and conservative process rlimits.
- Unit tests use mocks; the target Linux VPS must pass a real probe before host compatibility can be claimed.
- Process rlimits do not replace cgroups, seccomp, trusted service separation, or tool-side fencing. No real tools are authorized.
- Follow docs/SANDBOX_VALIDATION.md for non-root VPS validation.
