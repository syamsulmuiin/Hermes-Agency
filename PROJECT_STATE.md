# Hermes Agency — Project State

## Mission
Develop a secure, persistent, testable multi-agent runtime while preserving the six original agent prompt templates.

## Repositories
- Upstream (read-only): https://github.com/malvinjauhari/Hermes-Agency
- Fork: https://github.com/syamsulmuiin/Hermes-Agency
- Development branch: development/foundation
- Default branch main remains unchanged by this phase.

## Standing constraints
- Do not change features or behavior outside approved scope.
- Privileged, destructive, credential-related, and deployment actions require explicit authorization.
- Validate changes with tests; maintain rollback paths.
- Do not claim unexecuted actions or tests.
- Technical documentation in English; conversation in Indonesian.
- Preserve upstream attribution and license.

## Phase 1 status
- Fork verified with push permissions.
- Foundation prototype integrated into a separate development branch.
- SQLite tasks, handoffs, audit events; owner validation; deny-by-default example.
- Four local unit tests in tests/test_core.py.
- Original six agents and prompt files remain unchanged.
- Not merged into main or deployed.

## Known limitations
- No real LLM provider, tool execution, sandbox, durable scheduler, user approval flow, or self-improvement.
- set_status currently accepts any enumerated state transition; transitions and authorization need hardening.
- No handoff idempotency, payload size bounds, or audit integrity guarantees.
- Local tests are not a production security assessment.

## Phase 2: Security primitives (2026-11-06)
- Added agency/security.py: SQLite atomic task claims, expiring leases, fencing tokens, guarded state transitions, persisted single-use approvals bound to task/action/parameter digest.
- Added tests/test_security.py covering lease expiry, duplicate claims, stale tokens, unauthorized transitions, approval replay, denial, expiry, and restart.
- Local prototype of the same design passed six tests before upload. GitHub Actions verification of the committed files has not yet run.
- WARNING: caller-provided reviewer identities are not authenticated; approval must NOT authorize real tools yet.
- WARNING: task handoff guard is not yet transactionally integrated with the base handoff; concurrency hardening is still required.
- WARNING: lease tokens prevent stale task completion, but cannot stop external side effects from an already-running worker. Tool-side fencing and idempotency are required.
- No LLM integration, tool execution, deployment, or upstream modification.

## Phase 3: Atomic handoff and test automation (2026-11-06)
- Reworked SecureAgencyStore.handoff into a BEGIN IMMEDIATE transaction with owner/status/lease validation and bounded structured payloads.
- Added tests/test_hardening.py for concurrent claims, stale owner handoff, payload bounds and reviewer role gate.
- Added .github/workflows/foundation-tests.yml to run unittest on development/foundation pushes and main pull requests.
- Added docs/SECURITY_BOUNDARIES.md describing remaining trust-boundary and execution limitations.
- CI results have not been confirmed. Do not claim that the committed tests pass until a run is inspected.
- The AuthenticatedReviewer object is forgeable in-process and legacy decide() still accepts a reviewer string. Approval remains unsafe for real tools.

## Phase 4: Trusted Runtime Foundation (2026-11-06)
- Disabled public legacy approval decision and consumption methods on SecureAgencyStore.
- Added agency/trusted.py with HMAC-SHA256 expiring role-scoped credentials and transactional, one-time worker/lease/action-bound grant reservations.
- Updated tests/test_security.py and tests/test_hardening.py to use the new trusted boundary.
- Added tests/test_trusted.py covering credential tampering, expiry, replay, mismatched worker, stale lease and legacy bypass.
- Updated docs/SECURITY_BOUNDARIES.md.
- Verification BLOCKED: container cannot resolve github.com to clone the repository; GitHub Actions run results have not been confirmed. Do not claim test pass.
- Security BLOCKED: issue_credential must only be called after real server-side authentication. Signing key is not provisioned. Python in-process access is not an isolation boundary. No tools are connected.
- Next: verify CI and fix any failing tests; build authenticated API/session boundary with key rotation and protected storage; implement tool-side fencing/idempotency and sandbox; then orchestrator.

## Next milestones
1. Add transition graph and owner-aware authorization.
2. Add idempotency keys and transactional task claiming.
3. Add strict schema, size limits, and adversarial tests.
4. Implement actual policy enforcement and approval persistence before tools.
5. Introduce isolated execution, rollback, and recovery.
6. Add agent adapters and measurable learning only after safety gates.

## Continuation prompt
Read PROJECT_STATE.md, inspect the current branch and commits, run tests, preserve upstream templates and scope constraints, then continue the next unfinished milestone. Report evidence, limitations, and blockers.
