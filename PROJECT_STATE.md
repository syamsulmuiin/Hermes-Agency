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

## CI failure investigation (2026-11-06)
- Inspected full job logs for runs 42194877358, 42194864762, 42194842942, 42194809266, and 42194791882.
- All five jobs reached the unittest step; checkout and Python setup succeeded.
- Root cause: tests from earlier commits expected insecure legacy decide()/consume()/decide_authenticated() paths to work. These APIs were intentionally disabled for security.
- The latest committed tests/test_security.py and tests/test_hardening.py now use TrustedApprovalService and explicitly expect legacy rejection. These changes occurred after the listed failed runs.
- Added malformed base64 credential handling and regression coverage.
- Historical failed runs remain failed; a fresh workflow run on the latest commit is required to confirm resolution.
- Node.js 20 deprecation warning from checkout@v4 and setup-python@v5 is non-fatal and separate from the test failures.
- Do not re-enable insecure legacy approval paths to make tests green.

## Phase 5A: Tool-free orchestration foundation (2026-11-06)
- User reported latest GitHub Actions succeeded after the previous CI fixes. The GitHub connector did not independently return a successful push-run status for the latest branch commit; record user confirmation separately from verified CI evidence.
- Added agency/orchestrator.py with a deterministic, persisted six-agent route, transactional stage advance, single completion, duplicate-stage rejection, and restartable SQLite checkpoints.
- Added tests/test_orchestrator.py covering six-stage workflow, restart, replay, active leases, invalid results, and terminal state.
- No LLM calls, shell execution, network calls, file-writing tools, or deployment were connected.
- SECURITY LIMIT: advance() accepts an agent label without authenticating the caller; it is an internal prototype API only, not a public endpoint. No external actions may be attached to it.
- CI for the new orchestration commits is not yet confirmed. Do not claim the new tests pass until the latest run is inspected.
- Next: inspect fresh CI; build a trusted authenticated service boundary and key management, then implement tool-side fencing/idempotency and isolated sandbox before enabling real execution.

## Phase 5B validation checkpoint (2026-11-06)
- User reports latest GitHub Actions run successful. The previously added agency/runtime.py had no tests/test_runtime.py at the time of that run, so that success does not validate the runtime module.
- Added tests/test_runtime.py with grant mismatch, worker identity mismatch, stale lease, no-side-effects and key-file permission checks.
- The new test commit is not yet confirmed green in CI. Phase 5B remains incomplete pending these results.
- Runtime is dry-run only: no sandbox, authenticated server, key rotation or real tool adapter. Do not enable external execution.
- Next after successful runtime CI: implement trusted operator authentication, key lifecycle, and isolated tool adapter with OS-enforced sandbox and fencing. Retain fail-closed behavior.

## Phase 5C: Local operator authentication prototype (2026-11-06)
- User reports the latest GitHub Actions successful, including the Phase 5B runtime tests; this is user-reported rather than independently verified by a push-run query.
- Added agency/operator_auth.py: offline scrypt verifier provisioning, constant-time secret comparison, and short-lived approver credential issuance from the trusted service.
- Added tests/test_operator_auth.py: valid operator, wrong secret, short secret, and role separation.
- SECURITY LIMITS: operator gate is an in-process prototype; no HTTP/session authentication, rate limiting, MFA, secret storage automation, account lockout, key rotation, or sandbox.
- Never expose LocalOperatorGate or TrustedApprovalService.issue_credential to an agent. No real tools are connected.
- CI for Phase 5C commits remains unverified. Next: confirm tests, add hardened authenticated service boundary, secret lifecycle and OS-enforced sandbox; only then tool-side fenced execution.

## Phase 5D: Versioned key lifecycle foundation (2026-11-06)
- User reported previous Actions run completed; its exact run ID and logs were not provided, so successful completion of Phase 5C cannot be independently verified here.
- Added agency/keyring.py: in-memory versioned HMAC credential signing, explicit active-key rotation, retirement/revocation, role/audience/expiry validation, and fail-closed malformed-token rejection.
- Added tests/test_keyring.py covering rotation, old-key grace, retirement, tampering, role mismatch, expiry and invalid operations.
- New keyring is NOT yet integrated with TrustedApprovalService, operator gate, or persistent protected key storage; existing v1 credentials remain unchanged.
- No network API, sandbox, or real tool execution is enabled. CI for the Phase 5D commits remains to be checked.
- Next: validate latest CI; integrate keyring through a trusted server-only credential issuer, design persistent key storage and secure rotation procedure; implement sandbox before any external effects.

## Next milestones
1. Add transition graph and owner-aware authorization.
2. Add idempotency keys and transactional task claiming.
3. Add strict schema, size limits, and adversarial tests.
4. Implement actual policy enforcement and approval persistence before tools.
5. Introduce isolated execution, rollback, and recovery.
6. Add agent adapters and measurable learning only after safety gates.

## Continuation prompt
Read PROJECT_STATE.md, inspect the current branch and commits, run tests, preserve upstream templates and scope constraints, then continue the next unfinished milestone. Report evidence, limitations, and blockers.
