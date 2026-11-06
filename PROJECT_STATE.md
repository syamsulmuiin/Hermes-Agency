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

## Phase 5I.1: Trusted in-process stage execution (2026-11-06)
- Added agency/trusted_execution.py, requiring a valid worker credential whose verified identity equals the current stage agent before submitting structured results to the existing coordinator.
- Reuses TrustedApprovalService verification and enforces shared store identity; no shell/network/tool invocation.
- Added tests/test_trusted_execution.py for success, mismatched identity, approver-only role, invalid token and store mismatch. Committed; VPS/CI tests not yet verified.
- SECURITY LIMIT: credential issuance is a trusted-infrastructure operation, not an agent API. This in-process wrapper does not authenticate HTTP clients, authorize LLM-produced text, or prevent malicious code already running in the same Python process from bypassing it. No external agent endpoints should be exposed yet.
- Next: verify unit tests, introduce process-isolated authenticated server boundary and agent-specific non-mintable credentials; then connect constrained LLM adapters and audited tool broker.

## Phase 5I.2: Trusted boundary protocol preparation (2026-11-06)
- User reported successful build for Phase 5I.1; specific CI job/test count not independently checked.
- Added agency/trusted_protocol.py: strict, size-bounded, data-only stage request parser; no listener, no execution, no credential minting.
- Added tests/test_trusted_protocol.py covering valid input, invalid JSON and unexpected fields. Tests not yet verified.
- IMPORTANT: this is only protocol preparation, NOT a process-isolated trusted server. A future server must authenticate peers, keep signing keys inaccessible to agents, and enforce replay/credential expiry and filesystem permissions. No agent tools enabled.

## Phase 5I.3: Local trusted transport primitives (2026-11-06)
- User reported 60 unit tests passing in 1.504s for the prior milestone.
- Added agency/trusted_local_service.py: bounded single-request handler for an already accepted Unix-domain connection, with private owner-only socket-directory verification. Added tests/test_trusted_local_service.py for permission/symlink/input rejection.
- IMPORTANT: This is NOT a running service, an authenticated peer-credential check, or process isolation. The handler relies on existing worker credential validation in TrustedAgentExecution. A separate trusted supervisor must securely create/bind the socket, validate peer OS identity, enforce file/key/database isolation, and limit connections before production use.
- No agent tools enabled. New tests committed, not yet verified on VPS/CI.
- Next: implement peer-credential checked socket server with lifecycle controls and tests, then an unprivileged agent client and LLM adapter.

## Phase 5I.4: Kernel-verified Unix peer identity (2026-11-06)
- User reported prior Phase 5I.3 tests OK, without a detailed count.
- Added agency/trusted_peer.py: Linux SO_PEERCRED inspection and explicit UID allowlist check before delegating to the existing bounded stage handler. Added tests/test_trusted_peer.py for peer credentials and denied callers.
- No daemon or remote endpoint exists. This is an optional trusted-server building block; it is NOT yet wired to a production listener. The current UID check is not a complete process isolation guarantee; same-UID processes and inherited descriptors remain threats. Deployment must use distinct OS identities and private key/DB permissions. Worker credentials remain mandatory.
- Tests committed, not yet independently verified on VPS/CI. No tool execution enabled.
- Next: design a supervised socket listener with peer UID enforcement, lifecycle controls and restricted response framing; test separate OS-user processes and replay/timeout behavior.

## Phase 5I.5: One-shot Unix listener prototype (2026-11-06)
- User reports Phase 5I.4 tests OK; detailed counts unavailable.
- Added agency/trusted_listener.py, a one-connection Unix socket listener that checks an existing owner-only directory, refuses existing paths, validates UID allowlist and delegates to SO_PEERCRED + worker credential gates. Cleanup checks socket inode before unlinking.
- Added tests/test_trusted_listener.py covering existing pathname, invalid allowlist and malformed request over a real socket. New tests are committed but not yet verified on VPS/CI.
- SECURITY LIMIT: this is a one-shot prototype, NOT a supervised production daemon. Private 0700 socket directory prevents cross-UID clients, so separate OS-user process tests are still pending. Same-UID untrusted processes may reach socket but still need a valid worker credential. No credential issuer endpoint or tool execution.
- Next: test current suite, design controlled cross-UID socket access and trusted process startup with protected database and signing keys; test real separate OS users and crash/restart behavior before claiming isolation.

## Phase 5I.6: Bounded sequential local service (2026-11-06)
- User reports Phase 5I.5 tests OK; exact count not supplied.
- Added agency/trusted_service.py for finite sequential Unix socket requests (1-100), per-request peer UID and worker credential checks via existing boundary, idle timeout, conservative error handling, and inode-checked socket cleanup.
- Added tests/test_trusted_service.py for invalid limits and two rejected requests over a real socket. Tests committed; VPS/CI verification pending.
- LIMITATIONS: This is NOT an indefinitely running daemon, nor a complete cross-UID privilege boundary. It has no response protocol, supervised restart, OS account separation or trusted credential provisioning. No tool execution is enabled. A private 0700 directory currently allows only the owner to connect.
- Next: test this milestone; design proper separate-user transport and protected key/DB ownership, then implement an authenticated client and controlled lifecycle without weakening directory security.

## Phase 5I.7: Cross-UID transport policy (2026-11-06)
- User reports Phase 5I.6 tests OK, exact count not provided.
- Added agency/cross_uid_policy.py to validate pre-provisioned group-traversable (0710) Unix socket directory and group-writable (0660) socket ownership/modes, without changing permissions or privilege.
- Added tests/test_cross_uid_policy.py for denial of private directories, wrong groups and non-socket paths. New tests are committed but not yet verified on VPS.
- IMPORTANT: This is a policy validator, NOT cross-UID communication. Existing listeners still require owner-only 0700 directory and socket 0600; no cross-UID listener is wired yet. A dedicated client group, distinct OS users, separate private key/database directories, and real cross-user tests are required before activation. Do not use a shared group for secrets.
- Next: design an explicit cross-UID listener using a dedicated socket transport directory, keep key/DB directories 0700 server-only, and verify SO_PEERCRED + worker tokens with separate OS identities.

## Phase 5 consolidated validation (2026-11-06)
- User requested Phase 5 be treated as ONE integrated process rather than many small milestones, with ONE full test suite and commits. Do not ask for per-subphase manual tests.
- Added tests/test_phase5_integration.py: single end-to-end local Unix socket test combining SO_PEERCRED UID gate, role-scoped worker credential, rejected wrong-agent credential, persisted workflow advancement and socket cleanup.
- Existing GitHub Actions workflow already runs the entire unittest discovery suite on pushes to development/foundation. Use that workflow as the unified CI gate.
- This integration test uses the same OS UID in one process with a separate server thread. It does NOT demonstrate distinct-user process isolation, protected signing keys against untrusted agents, persistent daemon lifecycle, or any tool execution.
- Next consolidated Phase 5 acceptance: cross-UID real-process test with protected key/database ownership, authenticated agent client, audited broker denial tests and supervised service lifecycle; only then enable permitted effects. Keep shell execution disabled until isolated backend validated.
- New integration test committed; CI result must be verified before claiming full suite success.

## Phase 5 CI regression fix (2026-11-06)
- GitHub Actions run 42221295528 job 127903716647: 76 tests, 1 failure in test_phase5_integration.py. Root cause: SQLite connection created in main thread, used by trusted server thread (sqlite3.ProgrammingError).
- Fixed test to run serve_bounded on SQLite-owning main thread and move only socket client I/O to a background thread. No SQLite thread-safety override, security weakening, or production workflow changes.
- Fix commit bb687c41e2a8bba214075361a6a084364c89f472; new CI result pending verification. Continue using one full Phase 5 CI suite, not repeated manual per-subphase tests.

## Phase 5 consolidated continuation: cross-UID listener (2026-11-06)
- User reports consolidated Phase 5 build succeeded. Continue with one CI suite, no repeated subphase test requests.
- Added agency/cross_uid_listener.py to bind a Unix socket in a pre-provisioned 0710 trusted-owned transport directory with dedicated client group, validate resulting 0660 socket ownership/mode, require explicit allowed client UIDs distinct from the server, and enforce SO_PEERCRED plus worker credentials. It does not modify directory permissions, chown, grant credentials, or run tools.
- Added tests/test_cross_uid_listener.py for same-UID denial, wrong-group denial, and existing-path protection. Committed; latest CI verification pending.
- Still not proven: real separate-UID subprocess connectivity, server-owned private key/database directory, supervisor lifecycle and response acknowledgements. This one-shot listener is a security building block, not a deployed daemon. Keep tool execution disabled.
- Next: integrate a minimal authenticated client and real separate-UID process integration in a single CI acceptance test (only when suitable OS user provisioning is available), then supervised lifecycle.

## Phase 5 consolidated integration: unprivileged client (2026-11-06)
- Added agency/trusted_client.py and tests/test_trusted_client.py: strict size/schema validation and Unix-domain socket submission from an unprivileged client, without issuing credentials, accessing DB/keys or invoking tools.
- IMPORTANT: send_stage returning does NOT prove server accepted the stage; current server has no acknowledgement framing. Acknowledged authenticated protocol and separate-UID subprocess tests remain acceptance requirements.
- User requested a single consolidated Phase 5 CI gate; continue using existing GitHub Actions full unittest suite. These new tests are committed but CI result is not yet confirmed.
- Next: add bounded server acknowledgement protocol with no sensitive exception leakage; verify real distinct UID process connectivity and server-owned secret directory, then supervised lifecycle and consolidated acceptance.

## Phase 5 consolidated: acknowledged transport (2026-11-07)
- User reports prior GitHub Actions suite succeeded. Added agency/trusted_ack.py: bounded opaque accepted/denied response with no exception detail, tests/test_trusted_ack.py for accepted, denied and truncated acknowledgements.
- Added send_stage_confirmed() to agency/trusted_client.py; updated serve_bounded(..., acknowledged=True) as opt-in, preserving the previous default for compatibility. A client only reports success after an explicit accepted response; missing/malformed/denied responses fail closed.
- Code committed; new CI run not yet verified. This is NOT a production-grade authenticated server identity mechanism; socket path trust and deployment permissions remain critical. Cross-UID listener does not yet use the acknowledgement protocol. Separate OS-user integration and supervised service lifecycle remain outstanding; do not declare Phase 5 finished or enable agent tools.
- Continue using one full GitHub Actions test suite rather than separate per-subphase user tests.

## Phase 5 consolidated: acknowledged cross-UID listener integration (2026-11-07)
- User reports previous GitHub Actions success. Cross-UID one-shot listener now supports optional acknowledged=True, preserving previous default behavior. The trusted service sends only accepted/denied and does not leak internal exception text.
- Added tests/test_cross_uid_ack_integration.py to exercise accepted and denied socket requests, stage advancement only on acceptance, and socket cleanup. IMPORTANT: these tests MOCK kernel peer UID to exercise policy; they do not establish actual cross-UID OS isolation. New CI result pending.
- Final Phase 5 acceptance still requires actual separate-UID processes on VPS, verified private signing-key/SQLite permissions, and service lifecycle behavior. No agent tool execution enabled. Ask user for one consolidated VPS test only after the implementation and CI gate are ready.

## Phase 5 consolidated acceptance hardening (2026-11-07)
- User reports prior GitHub Actions run passed. Added tests/test_confirmed_workflow_integration.py: real TrustedApprovalService worker credentials, SQLite workflow handoff, Unix socket and explicit denied/accepted acknowledgements in one end-to-end CI test. The trusted SQLite connection stays in the server-owning test thread.
- Added agency/private_state.py and tests/test_private_state.py: read-only validation of service-owned 0700 trusted/key directories, 0600 SQLite DB and auxiliary files, rejecting symlink key directory and exposed state. This validator is NOT yet wired to a production service bootstrap; it does not provision users or permissions.
- New CI status unverified. Actual separate-UID process connectivity, server process lifecycle and supervisor remain to be tested; do not declare Phase 5 complete or enable tool execution. Request one consolidated VPS acceptance session only when deployment implementation and CI are ready.

## Phase 5 consolidated: protected startup gate (2026-11-07)
- User reports previous CI succeeded. Cross-UID one-shot listener now optionally accepts trusted_state=(private_directory, sqlite_database, key_directory), validating private-state ownership and permissions before any socket bind. Existing calls remain compatible. The validator does not provision users, repair permissions or run tools.
- Added tests/test_cross_uid_startup_gate.py: unsafe database permissions, missing private state, and invalid configuration fail before socket creation.
- This is opt-in for the library entrypoint; a production launcher must require trusted_state unconditionally and verify trusted service runs as a distinct non-root UID. New CI status pending.
- Still required before Phase 5 acceptance: supervised launcher, actual cross-UID subprocess communication and verified key/DB isolation, one final VPS test. Do not enable tool execution.

## Phase 5: mandatory protected service entrypoint (2026-11-07)
- User reports prior GitHub Actions successful. Added agency/protected_service.py: serve_protected_once enforces non-root trusted service UID, explicit distinct allowed client UIDs, mandatory protected SQLite/key directory validation, and acknowledged cross-UID transport. Legacy library functions remain unchanged for existing tests.
- Added tests/test_protected_service.py for fail-closed startup and acknowledgement wiring. This is a callable entrypoint, NOT an installed systemd daemon, OS user provisioning tool, or a complete production launcher; no tools enabled. New CI status pending.
- Next: design and test supervised lifecycle and actual separate-UID process acceptance. Request one consolidated VPS validation session after CI and deployment packaging are ready; do not repeatedly ask for manual tests.

## Phase 5: deployment preflight CLI (2026-11-07)
- User reports prior GitHub Actions successful. Added agency/deployment_preflight.py as a read-only CLI (`python -m agency.deployment_preflight --transport-dir ... --state-dir ... --database ... --key-dir ... --client-gid ... --allow-uid ...`) checking non-root identity, explicit distinct client UIDs, trusted SQLite/key permissions and pre-provisioned transport directory ownership/mode. It does not create users, files, sockets or services, or enable tools.
- Added tests/test_deployment_preflight.py. New CI result pending. This CLI validates filesystem configuration, not actual cross-UID communication or daemon lifecycle.
- Remaining Phase 5: supervised protected service bootstrap, actual separate-UID integration, credential/DB isolation and one final VPS acceptance. Do not request incremental VPS tests; provide a single test bundle only after CI is ready.

## Single-VPS implementation checkpoint (2026-11-07)
- Deployment scope: exactly ONE active VPS. Migration is stop/backup/restore/start to replacement VPS; old VPS must remain stopped. Separate Linux UIDs are local process isolation, NOT multi-VPS clustering.
- Added agency/single_vps_service.py: runnable one-shot trusted Unix socket process with mandatory non-root preflight, service-owned SQLite connection, protected secret file (0600, 64 raw bytes), and acknowledged protected listener. The process exits after one request; a supervisor/continuous serving lifecycle is NOT yet implemented. The CLI does NOT issue worker credentials, create tasks, or execute agent tools.
- Added tests/test_single_vps_service.py for fail-closed startup and resource cleanup. New GitHub Actions result pending.
- CRITICAL remaining blockers to calling the system production-ready: persistent supervised lifecycle; trusted credential issuance and task creation operator workflow; actual distinct-UID subprocess integration and file isolation; independent sandbox enforcement for tool execution; final VPS acceptance. Do not claim six autonomous LLM agents or sandboxed tools work: current six-agent workflow is deterministic and tool-free.
- Immediate acceptance path: GitHub Actions must pass; then provision dedicated non-root service/client accounts and test full process separation on the single VPS. No secrets or permissions should be loosened for testing.

## VPS unittest root fixture correction (2026-11-07)
- VPS reported 107 tests, one ERROR in test_deployment_preflight.test_valid_permissions. Root-owned temporary directories were incorrectly checked with mocked effective UID 1000, producing a false owner mismatch. Corrected the test to use the actual UID; root must fail the non-root gate, while non-root fixtures may pass. No production permission policy was changed.
- Fix commit ecf2c6e096bf86386e5ecc16b42693a347471b61; full post-fix CI/VPS rerun pending. Continue Phase 5 only after rerun passes.

## Single-VPS finishing continuation (2026-11-07)
- User reports 107 unit tests passed after root-fixture correction. Added agency/service_lifecycle.py continuous sequential serving: idle socket timeouts are retried, unexpected errors fail closed, and a stop predicate is testable. Added optional `--forever` to agency/single_vps_service.py (default one-shot unchanged).
- Added tests/test_service_lifecycle.py and docs/SINGLE_VPS_DEPLOYMENT.md. New CI result is pending; no claim of full validation.
- This is NOT completion of autonomous six-agent operation: current worker results are caller-supplied, credential provisioning is external, no independently isolated tool executor exists, and actual distinct-UID and restart acceptance remain untested on VPS. Never enable unsafe host command execution as a shortcut.
- Next concrete acceptance: verify latest CI, provision dedicated local UIDs/group/secret with approved operator procedure, run one consolidated VPS acceptance for service lifecycle, UID isolation, database protection, and acknowledgements. Build autonomous AI/approval/tool capabilities separately behind sandbox gates. Single VPS only; no clustering.

## Single-VPS host acceptance and documentation checkpoint (2026-11-07)
- User-provided VPS output: development/foundation commit 6f8c37c, Python 3.12.3, 110 unittest tests passed. systemd hermes-agency.service active under hermes-trusted (UID 997), group hermes-agents (GID 987); hermes-worker UID 995 connects to trusted.sock (0660). Worker read access to agency.db and signing.key denied. Deployment preflight passed.
- README.md, README-id.md, and docs/SINGLE_VPS_DEPLOYMENT.md updated to distinguish prompt templates, verified trusted runtime, and unfinished autonomous capabilities. Fork clone links corrected while upstream attribution retained.
- Known operational gap: /run/hermes-agency was manually provisioned; reboot-time recreation has not been configured/verified. The running /opt/hermes-agency copy does not update when GitHub branch is committed or /root/Hermes-Agency is pulled.
- Still open: signed cross-UID stage acceptance and rejection on VPS, unauthorized UID check, workflow restart persistence, restart-on-failure/boot test, trusted operator provisioning, independent OS-enforced sandbox, LLM-backed six-agent execution, tool-side fencing. Do not call autonomous system complete.
- Documentation-only commits do not require restarting the live service. New GitHub Actions result for documentation commits not yet inspected.

## README scope and boot directory fix (2026-11-07)
- Removed experimental single-VPS runtime sections from both README.md and README-id.md as requested. Detailed truthful runtime status remains in docs/SINGLE_VPS_DEPLOYMENT.md and PROJECT_STATE.md.
- Added deploy/hermes-agency.tmpfiles.conf to recreate /run/hermes-agency at boot with 0710 hermes-trusted:hermes-agents; deployment guide now includes explicit installation instructions and cautions about /opt runtime copy. Not installed or reboot-tested yet.
- No change to live VPS service or agent execution permissions. New GitHub Actions result pending. Next: consolidate cross-UID authenticated workflow and restart acceptance tests, then independently isolated agent execution; do not claim autonomy complete.

## Live negative-auth smoke test preparation (2026-11-07)
- Added deploy/smoke_negative_auth.py: a worker-UID, no-secret, no-task-creation live probe using a deliberately invalid credential and unknown task ID. Requires an explicit denied acknowledgement; retries short socket rebind gaps. Does not exercise valid credential acceptance or task state transitions.
- Pending: user runs the script on VPS, verifies service remains active, then trusted-only operator provisioning and end-to-end positive workflow test can be designed without exposing signing secrets to workers.
- The live /opt/hermes-agency service code has not been updated or restarted by these repository commits. No host test result is claimed.

## Live negative-auth verification (2026-11-07)
- VPS operator ran deploy/smoke_negative_auth.py as hermes-worker from a root-readable staging location under /tmp; INVALID_CREDENTIAL_DENIED=PASS, exit code 0, and hermes-agency.service remained active.
- Initial attempt directly from /root/Hermes-Agency failed with permission denied, consistent with worker isolation; no security permissions were relaxed. Staging script was removed after test.
- This proves only denial of that invalid credential via the live socket. Valid credential acceptance, mismatched agent identity, unauthorized UID, workflow persistence across restart, and reboot recovery remain unverified.

## Positive trusted workflow integration test preparation (2026-11-07)
- Added tests/test_positive_trusted_workflow.py with isolated temporary SQLite database and random ephemeral signing key. Credentials are issued by TrustedApprovalService in trusted test setup, not by worker input or public socket.
- Tests cover valid worker stage acceptance, workflow persistence across closing/reopening the SQLite store, denial of wrong agent identity, denial of forged credential, and denial of approver-role credential. Denied stages must not advance workflow or create handoffs.
- This is an in-process integration suite, not yet a live cross-UID Unix socket positive test or systemd restart test. GitHub CI/VPS test execution pending. Live service database and signing key are untouched.
- Next gate: run tests; design operator-only credential provisioning and a live cross-UID test with a dedicated test workflow and no credential leakage or tool execution.

## VPS positive integration verification (2026-11-07)
- Operator pulled commit e73dc7c on VPS and ran tests.test_positive_trusted_workflow: 3/3 tests passed.
- Full suite: 113 tests passed in 1.500 seconds; hermes-agency.service remained active.
- Verified isolated trusted-issued worker credential, positive stage progression, SQLite close/reopen continuity, wrong identity/forged credential/approver-role denial. This does not yet prove positive cross-UID socket operation or systemd restart recovery.
- Next acceptance: operator-controlled credential issuance outside worker, live socket positive test on dedicated test workflow, and restart persistence; no agent tools or production autonomy implied.

## Prepared live cross-UID positive E2E test (2026-11-07)
- Added deploy/live_positive_e2e.py. Root operator orchestrates separate hermes-trusted (task creation, short-lived credential issuance, SQLite verification) and hermes-worker (socket submission) processes. Signing key stays in trusted process; only worker credential crosses stdin; neither token nor signing key is logged or placed in argv/environment. It uses a dedicated test workflow in the existing SQLite database and does not run agent tools or restart the service.
- Requires root to stage this standalone script outside /root (e.g. /tmp mode 0644) and /opt/hermes-agency code to be present. Test creates a durable audit/test workflow record; not a zero-write probe. Run only with explicit operator acceptance of this test data.
- No live execution result yet. Pending VPS operator run and validation; do not claim cross-UID E2E passed before output.

## Live cross-UID positive E2E verified on VPS (2026-11-07)
- Operator pulled commit 25db948 and ran deploy/live_positive_e2e.py using a root-readable staged copy. Output: CROSS_UID_VALID_CREDENTIAL=PASS, SQLITE_WORKFLOW_ADVANCED=PASS, LIVE_E2E=PASS, TEST_EXIT_CODE=0; hermes-agency.service remained active.
- Verified trusted-only signing key access, short-lived worker credential passed to separate UID, authenticated live Unix socket submission, and persisted CEO-to-PM workflow transition in SQLite. This creates one durable test workflow record.
- Still unverified: systemd restart persistence and reboot recovery. Independent sandbox, tool execution, LLM-driven agents and autonomous operations remain unimplemented.

## VPS systemd restart persistence verified (2026-11-07)
- Operator measured SQLite workflow_progress count=1 and handoffs count=1 before restart; after systemctl restart hermes-agency.service both counts remained 1.
- systemctl is-active reported active; /run/hermes-agency ownership hermes-trusted:hermes-agents and mode 0710 remained correct.
- This verifies basic restart persistence and transport directory ownership, not reboot recovery, socket availability post-restart, or active in-flight task recovery.
- Next development phase: independent sandbox design and incremental fail-closed implementation, without altering existing live trusted service until independently validated.

## Independent sandbox implementation checkpoint (2026-11-07)
- Added agency/sandbox_preflight.py: read-only Linux namespace prerequisite inspection; never treats namespace presence as proof of isolation, never enables tools.
- Added tests/test_sandbox_preflight.py: missing namespace prerequisites, simulated prerequisites, and invalid report all fail closed.
- No actual sandbox runner, filesystem/network isolation, LLM or tool execution implemented. Tests not yet run on VPS. This checkpoint is NOT a finished independent sandbox or finished Hermes-Agency.
- Next: implement and independently validate a real isolated runner, resource ceilings, filesystem/network denial and escape tests before any tool access; then integrate LLM/agent execution behind existing trusted boundary.

## Rootless namespace sandbox probe implementation (2026-11-07)
- Added agency/linux_sandbox.py: fixed, non-tool isolation probe running in a separate non-root process; Linux user, mount, UTS, IPC, network and PID namespaces, private mounts, empty tmpfs chroot, CPU/memory/file-size/FD limits and no_new_privs. It fails closed on any missing kernel permission or isolation check. No Docker, Podman or Bubblewrap.
- Added tests/test_linux_sandbox.py for root refusal, invalid limits, denied isolation and forged evidence.
- This is an actual attempted isolated *probe*, not a general agent command runner. No arbitrary agent code/tools, seccomp filter, cgroup enforcement, safe bind mounts or network policy are implemented. Rootless user namespaces may be disabled on the VPS. No live VPS isolation result or full suite result yet; do not claim readiness.
- Next: run tests and live probe as hermes-worker from deployed Python module; verify namespace isolation and kernel policy, then implement narrowly allowlisted tools only after escape/resource tests and approvals.

## Stale socket recovery patch (2026-11-07)
- VPS reported systemd auto-restart loop: FileExistsError for /run/hermes-agency/trusted.sock. Operator manually recovered stale socket and service returned active.
- Added agency/stale_socket.py and wired cross_uid_listener to attempt recovery only for a same-UID socket that refuses connection; regular files, symlinks, foreign-owner sockets, and accepting sockets are rejected. Added regression tests and updated existing expected exception.
- Caveat: inode recheck does not make unlink atomic against a competing process. The single-instance systemd supervisor remains a required assumption; do not expose listener creation to untrusted concurrent callers.
- Patch not yet deployed to /opt/hermes-agency or validated on VPS. Sandbox user namespaces remain denied by AppArmor policy; no global AppArmor changes authorized.

## VPS acceptance and sandbox follow-up (2026-11-07)
- Operator ran full regression suite: 126/126 PASS; installed stale socket patch into /opt/hermes-agency; PATCH_IMPORT=PASS; service active after restart; DEPLOYMENT=PASS. Backup: /tmp/hermes-rollback.et0mme. Live stale socket restart simulation not yet verified.
- Rootless worker unshare --user --map-root-user true failed writing uid_map with EPERM; host has kernel.apparmor_restrict_unprivileged_userns=1. No global AppArmor changes authorized.
- Corrected sandbox bug: host UID/GID must be captured before CLONE_NEWUSER, with regression guard. This change is committed but not yet validated on VPS. Sandbox remains probe-only, no agent tool execution and no verified isolation on this host.

## Adaptive sandbox portability milestone (2026-11-07)
- Added agency/adaptive_sandbox.py: host inventory and deterministic backend planning for rootless namespace, bubblewrap, systemd, podman and docker. Presence and caller-provided evidence are NOT trusted execution attestations; tools always remain disabled.
- Added five tests to ensure unsupported, forged/incomplete and merely installed backends cannot enable tools. VPS test run pending; previous accepted suite 127/127.
- Next: implement independently verified per-backend execution probes and policy-specific attestations, then a bounded executor with filesystem/network/process/resource isolation; no global AppArmor relaxation.

## Sandbox Validation Engine, fixed-probe stage (2026-11-07)
- VPS accepted adaptive planning milestone: 132/132 tests PASS and trusted service active.
- Added agency/sandbox_validation.py to attempt only existing fixed rootless namespace and bubblewrap probes, with bounded timeout, safe failure reasons, and fail-closed agent execution. Systemd/Podman/Docker remain explicitly unimplemented; no generic tool execution or privileged daemon probing.
- Added five tests covering timeout validation, successful probes not granting tool execution, safe failure classification, root refusal and invalid report.
- Pending: VPS regression (expected 137 tests), real non-root probe, AppArmor-compatible isolation backend, stronger attestations and resource/network/process isolation before tools can be enabled. No production deployment performed.

## Fixed-job isolated process executor (2026-11-07)
- Added agency/isolated_jobs.py: executes two fixed built-in jobs (noop, identity) as actual subprocesses under bubblewrap with namespace isolation, read-only /usr, no host shell, cleared environment, rlimits, timeout and bounded stdout. Any backend failure denies execution; no host fallback.
- Added six regression tests for allowlist, root/timeout rejection, missing backend, isolated invocation and failed backend. VPS verification pending (expected 143 tests).
- IMPORTANT: current VPS previously failed bubblewrap probe, so actual execution is expected to fail closed until an approved backend works. This does NOT implement general agent tool execution, seccomp, cgroups or complete resource confinement. No production runtime deployment.

## Operator-only systemd execution backend (2026-11-07)
- VPS rootless Bubblewrap failed loopback RTM_NEWADDR and uid_map Permission denied. Do not weaken AppArmor or host namespace policy.
- Added agency/systemd_jobs.py for two immutable diagnostic jobs through systemd-run transient services with DynamicUser, PrivateNetwork, strict filesystem protection, capabilities removed, runtime and resource limits. Root operator only; no sudo permissions granted to agents and no integration into trusted service.
- Added six regression tests. VPS regression expected 149 tests; actual systemd-run validation pending. This is a constrained executor, NOT production-grade arbitrary agent execution; inspect transient unit properties and verify host filesystem/network isolation before enabling further capabilities.

## Systemd acceptance and trusted admission (2026-11-07)
- VPS confirmed 149 tests PASS; operator-only systemd noop and identity executed, DynamicUser UID 62210, trusted service active.
- Added agency/systemd_acceptance.py: root-operated real transient service verifies non-root UID, /etc/shadow unreadable, /root inaccessible, /usr nonwritable, AF_INET socket denied; all must pass or acceptance fails. Still no claim of full PID/cgroup isolation, and acceptance is not an authorization token.
- Added agency/trusted_job_admission.py: credential-verified, role-matched, explicit-approval-gated fixed-job admission returning admitted_not_executed; no root execution or new service endpoint. Integration is intentionally partial until an independently provisioned privileged broker and durable authorization/audit protocol exist.
- Added six tests. VPS regression expected 155; real acceptance test pending. Production trusted service unchanged.
