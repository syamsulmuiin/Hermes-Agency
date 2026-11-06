# Security boundaries

The current foundation is a local prototype, not an authorization service.

- SQLite BEGIN IMMEDIATE serializes claims, state changes, and handoffs across local connections.
- Fencing tokens protect database state from stale workers. They do not prevent a stale worker from producing external side effects.
- Handoff payloads are bounded and validated, but no signed provenance or idempotency key exists yet.
- Approvals are persisted and one-time, bound to task, action, and parameters. They do not currently authenticate reviewers.
- AuthenticatedReviewer is a data holder, **not proof of authentication**. Do not construct it from user-supplied identities.
- The legacy decide(approval, reviewer, allow) API still accepts a string; it must be removed or restricted before attaching tools.
- Never expose consume() as a general authorization endpoint without binding the authenticated actor, active lease, and tool call in one trusted transaction.
- No shell, network, deployment, secret-access, or filesystem-write tool is wired to this package.
- Do not use this package for privileged execution until a trusted API identity boundary, tool-side idempotency, and sandbox have been tested.
