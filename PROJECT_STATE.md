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

## Phase 5E/5F: Integration, protected keys and sandbox probe (2026-11-06)
- Added tests/test_keyring_integration.py covering approval flow with key rotation and legacy-token rejection.
- Added agency/key_storage.py and tests/test_key_storage.py. Administrator-provisioned private key directory must be owner-only; key and manifest files are loaded with no-follow protections. No secret material is committed.
- Added agency/sandbox.py and tests/test_sandbox.py. The only sandbox invocation is a fixed Linux bubblewrap /bin/true isolation probe. It is not an agent command runner, and does not allow arbitrary commands, network access, or writable host binds.
- CI check of latest commit returned no combined status entries; this does not prove GitHub Actions success or failure. User must provide latest workflow run URL/ID for job-log verification, or inspect the Actions UI.
- Sandbox has NOT been executed on the target Linux host; kernel/user namespace/bubblewrap support remain unknown.
- SECURITY GATES STILL OPEN: runtime authorization is in-process, keyring persistence and rotation are administrator-managed, no authenticated remote service, no tool-side fencing or crash-safe idempotency, no resource-limit proof or isolated writable workspace. No external agent tools are enabled.
- Next: verify latest CI logs, test bubblewrap probe on the target Linux host, harden sandbox resource controls, implement trusted service boundary and tool-side fencing before any real tool execution.

## Phase 5G: Sandbox hardening and host validation (2026-11-06)
- Prior GitHub Actions run 42200171405, job 127833207663, independently verified successful: 42/42 unittest tests passed. This run predates Phase 5G commits.
- Updated agency/sandbox.py with conservative process rlimits, fixed /bin/true probe, empty environment, timeout and fail-closed behavior. No agent-selected commands.
- Extended tests/test_sandbox.py to assert rlimit hook and empty environment.
- Added docs/SANDBOX_VALIDATION.md with non-root Linux VPS procedure; updated README.md and docs/SECURITY_BOUNDARIES.md.
- Phase 5G CI and actual VPS isolation are NOT YET VERIFIED. Request latest run and host output before claiming completion.
- No real tool execution. Outstanding: trusted process separation, OS-specific namespace verification, cgroup limits, tool-side fencing and crash-safe idempotency.

## Phase 5G VPS diagnostic (2026-11-06)
- First actual VPS probe failed: bwrap execvp /bin/true: No such file or directory.
- VPS output confirms merged-/usr: /bin -> usr/bin, /lib -> usr/lib, /lib64 -> usr/lib64; /usr/bin/true exists.
- Updated sandbox mount layout to bind /usr read-only and recreate the three links inside sandbox. Unsupported layouts fail closed.
- Extended sandbox regression assertion. Latest CI and VPS rerun for this fix are pending.
- IMPORTANT: VPS test so far ran as root. A non-root test is mandatory before declaring Phase 5G validated.

## Phase 5G VPS retest and regression fix (2026-11-06)
- User ran real Bubblewrap probe on VPS as root: SUCCESS, {'isolated_probe': True, 'agent_tools_enabled': False, 'resource_limits': 'rlimit-probe-only'}.
- The same VPS run completed 42 unit tests with 1 error: test_failed_isolation_denied mock omitted stderr after diagnostic improvement; this is a test-fixture error.
- Updated tests/test_sandbox.py failed-process mock to include stderr (commit 47a32063). Fresh CI and VPS unit test results are pending.
- Non-root VPS validation is still mandatory. No arbitrary agent tool execution is enabled.

## Next milestones
1. Add transition graph and owner-aware authorization.
2. Add idempotency keys and transactional task claiming.
3. Add strict schema, size limits, and adversarial tests.
4. Implement actual policy enforcement and approval persistence before tools.
5. Introduce isolated execution, rollback, and recovery.
6. Add agent adapters and measurable learning only after safety gates.

## Continuation prompt
Read PROJECT_STATE.md, inspect the current branch and commits, run tests, preserve upstream templates and scope constraints, then continue the next unfinished milestone. Report evidence, limitations, and blockers.


## Cross-VPS portability checkpoint (2026-11-06)
- User requires portable operation across VPS providers, without per-host AppArmor changes.
- VPS evidence: Bubblewrap fixed probe succeeded as root; non-root failed with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. Kernel audit recorded AppArmor userns transition to `unprivileged_userns`; unshare UID mapping failed with EPERM. Exact policy enforcement path is not fully established.
- Added `sandbox_capabilities()` reporting a safe disabled backend and machine-readable reason on unsupported/denied hosts; added three mock-based tests and documented usage.
- No host security policies were changed. No fallback executor exists; this change does not make all VPS compatible or enable tools.
- Pending: latest CI verification, real non-root report, design and implement independently secured alternate backend(s), per-backend runtime validation, cgroups/seccomp, tool-side fencing, trusted service boundary.


## Verified VPS portability test (2026-11-06)
- User executed `python3 -m unittest discover -s tests -v` on VPS: **45 tests, OK** (3.958 s).
- User executed `sandbox_capabilities()` as non-root `nobody` on Linux x86_64: `bubblewrap_installed=True`, `backend=disabled`, `isolated_probe=False`, `agent_tools_enabled=False`, `reason=host_namespace_policy_or_isolation_denied`.
- Verified: capability reporting fails closed and provides a portable diagnostic. Not verified: any functioning non-root isolated executor on this VPS or compatibility across all VPS.
- Next: implement and test a genuinely isolated alternative backend under the same policy, or retain safe-only mode when none is available. No host policy changes or privileged agent execution.

## Phase 5H: Independent sandbox discovery (2026-11-06)
- Reviewed NousResearch/hermes-agent environment architecture, especially tools/environments/docker.py and docker_egress.py. This project does not import Hermes Agent or rely on Bubblewrap for the new backend discovery.
- Added agency/independent_sandbox.py: read-only Docker CLI candidate detection and unconditional fail-closed execution guard; no Docker socket access, host shell fallback, or arbitrary agent execution.
- Added tests/test_independent_sandbox.py with three regression tests. These tests are committed but CI/VPS results are not yet verified.
- IMPORTANT: Docker candidate detection is not container isolation. Existing Bubblewrap probe remains unchanged; no independent executable backend exists yet.
- Next: design a trusted privileged broker and strictly constrained container runner; verify daemon policy, mounts, network, user IDs, cgroups and side-effect fencing; run real non-root tests before enabling tools.

## Phase 5H VPS check and Podman candidate (2026-11-06)
- User reported unit tests OK and real independent discovery on VPS: Linux, Docker CLI absent, backend disabled, no tools enabled. Exact unit test count was not supplied.
- Added Podman candidate discovery alongside Docker; neither CLI presence nor rootless label authorizes execution. Added regression test, not yet verified in CI/VPS.
- Neither Docker nor Podman backend is implemented as an executor. Existing Bubblewrap probe is unchanged. Do not claim sandbox migration complete.
- Next: test updated suite and inventory; evaluate supported rootless container isolation with real host tests. On restricted VPS, refuse unsafe host fallback.

## Phase 5H.3: Portable tool-free runtime (2026-11-06)
- VPS user reports unit tests OK and independent backend discovery shows neither Docker nor Podman CLI installed. No isolated executor is available.
- Added agency/portable_runtime.py as a small wrapper around the existing persisted WorkflowCoordinator; workflow availability is independent of sandbox availability, while external tools remain disabled.
- Added three unit tests for type validation, disabled sandbox capability reporting, and delegation. Tests committed but not yet independently executed on VPS/CI.
- SECURITY LIMIT: this is not an LLM runtime; submit_stage_result is internal-only and unauthenticated. Do not expose it to remote callers. No real agent execution, shell, network, or filesystem tools are enabled.
- Next: validate tests; add authenticated trusted service boundary; implement sandboxed tool broker with actual isolation validation before enabling external effects.
