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

## Experimental persistent systemd broker (2026-11-07)
- VPS confirmed 155/155 tests, five systemd acceptance checks PASS, trusted service active.
- Added agency/systemd_broker.py: one-shot Unix peer UID check, strict fixed-job JSON, SQLite BEGIN IMMEDIATE one-time approval consumption before execution, durable started/completed/failed audit entries, systemd fixed-job executor. Five unit tests added; expected 160 tests, VPS validation pending.
- SECURITY: Prototype only. No root service deployment, no approval issuance API, no agent integration. Ledger filesystem ownership, socket directory trust, durable approval provenance, crash recovery, connection response behavior and bounded service lifecycle require further hardening before production. Do not grant workers sudo or direct broker access.

## Broker hardening milestone (2026-11-07)
- VPS confirmed 160/160 tests and trusted service active before milestone.
- Broker now rejects unsafe SQLite ledger ownership/modes before execution, adds root-only manual approval provisioning and Unix socket integration tests (peer UID, strict framing, replay, audit, disallowed job). Expected 167 tests; VPS validation pending.
- IMPORTANT: still a non-production prototype. Ledger initialization is not yet hardened against permissive initial file creation, root-only approval provisioning is not cryptographically linked to TrustedApprovalService decisions, broker socket lifecycle is not deployed as a protected systemd unit, and no end-to-end trusted-service-to-root-broker execution is wired. Do not deploy or grant agent access. Next milestone must address these before production activation.

## Real broker execution integration milestone (2026-11-07)
- Baseline VPS: 167/167 tests PASS, systemd sandbox acceptance PASS, trusted service active.
- Broker ledger initialization now exclusive O_EXCL/O_NOFOLLOW in a root-owned non-group-writable directory; private socket path directory checked and socket chmod 0600. Added tests for overwrite refusal, unsafe ledger, non-root operator E2E refusal (expected 170 tests).
- Added `python3 -m agency.systemd_broker_e2e`: opt-in ROOT-ONLY diagnostic using a root-owned temporary SQLite ledger, synthetic operator-provisioned one-time approval, Unix socket peer credentials, REAL systemd noop, consumed approval and persisted audit. It does NOT touch production service or prove trusted-service-to-broker authorization. VPS real execution pending.
- BLOCKER: full trusted-service integration not yet implemented. Existing `TrustedJobAdmission.admit(..., approved=True)` is not valid production approval provenance. Do not expose it as broker authorization. Broker must validate an actual durable approved grant bound to task/job/worker/lease, and broker lifecycle must be separately hardened before production activation. Never enable agent tool execution based solely on these tests.

## Trusted-signed broker grant milestone (2026-11-07)
- Baseline VPS: 170/170 PASS, real operator socket→systemd E2E PASS, sandbox acceptance PASS, trusted service active.
- `agency/broker_grants.py`: issue_broker_grant calls existing TrustedApprovalService.grant for actual approved task/action/params, authenticated worker and valid lease token, then signs bounded 60s max grant containing task, worker, lease generation, approval, job, params hash and unique grant ID. Dedicated HMAC key required; never agent-owned.
- `agency/systemd_broker.py`: execute_signed_grant validates signature, job binding and expiration, atomically persists grant consumption and status before real fixed-job execution. Replay rejected after success/failure. Seven negative/positive tests added; expected 177 tests, VPS pending.
- SECURITY BLOCKERS: not yet connected to broker Unix socket handler or production trusted service transport; no dedicated key distribution/rotation, broker-side current lease revocation check, operator approval issuer service, or safe production deployment. Signed grant verification proves authenticity at issuance, not ongoing lease validity. Do not enable agent execution. Existing legacy operator approval route remains separate.

## Signed broker socket + live lease fencing (2026-11-07)
- Baseline VPS 177/177 PASS and trusted service active before this change.
- Added separate `handle_signed_connection` Unix socket handler accepting only a signed grant from matching SO_PEERCRED UID, with strict newline framing and no legacy fallback.
- Broker verifies signed claims, then reads live trusted SQLite `task_leases`, task state, and `execution_grants`/approval provenance before atomic grant consumption and execution. Missing/expired/revoked lease, generation mismatch, forged job, wrong peer and replay deny.
- Five new tests exercise actual TrustedApprovalService approval -> lease -> issued grant -> Unix socket -> simulated fixed job, plus negative cases. Expected 182 tests; VPS validation pending.
- NOT YET PRODUCTION: handler is not wired to a privileged listener/service; key provisioning and secure cross-UID socket permissions not deployed; lease check and broker consume are not a single cross-database atomic transaction (revocation race possible). Test uses simulated executor, not real systemd. Do not enable autonomous agent execution until those blockers are resolved and tested.

## Production boundary hardening progress (2026-11-07)
- VPS baseline confirmed 182/182 PASS, trusted service active before this patch.
- Signed execution now opens trusted SQLite with mode=rw, holds BEGIN IMMEDIATE during live lease verification and fixed-job execution, and rolls back lock afterward. This prevents SQLite-mediated lease revocation between validation and job completion (including WAL mode), but may temporarily block trusted writers; execution remains fixed/short-lived.
- Added test for concurrent lease deletion blocked during execution; expected 183 tests, VPS pending.
- Remaining: secure dedicated cross-UID broker socket listener (not yet deployed), key provisioning/rotation, live service transport, production multi-process E2E and operator-controlled rollout. No autonomous tool enablement. Never claim production FINISH.

## Isolated signed broker deployment package (2026-11-07)
- VPS baseline before patch: 183/183 PASS; trusted service active. New code not yet run on VPS.
- `agency/signed_broker_service.py`: root-only one-shot dedicated signed socket 0660 root:trusted primary GID under root:trusted 0710 directory, SO_PEERCRED UID enforced by handler. Root-owned 0640 key (trusted primary GID), exclusive provisioning, NOFOLLOW, strict ownership/mode verification. Worker must not belong to trusted primary group. No legacy approval protocol exposed.
- `agency/full_broker_acceptance.py`: opt-in ROOT-only temporary multiprocess acceptance; trusted UID creates a REAL task, lease, approved request and signed grant; root broker executes actual systemd fixed noop; worker UID denied at bound socket; persistent broker consumption verified. This does NOT touch live service. Run `python3 -m agency.full_broker_acceptance` only on an operator-approved VPS test window.
- Added five unit tests; expected 188 total, VPS pending. Existing signed-grant unit tests cover expiration and replay; full multiprocess harness currently exercises successful real execution and worker socket denial, NOT separate live expired/replay socket attempts.
- NOT PRODUCTION COMPLETE: dedicated key is distributed through root:trusted GID but not rotated; live trusted service transport not wired; one-shot listener is an operator acceptance utility, not a supervised hardened production daemon. No autonomous tool enablement. Need VPS acceptance, then supervised service/key rotation and full negative multi-process cases before rollout.

## Broker negative multiprocess acceptance (2026-11-07)
- User VPS verified 188/188 regression PASS, real trusted approval -> root broker -> systemd PASS, worker socket denied, persistent grant consumed, service active.
- New acceptance now starts fresh root broker listeners after successful job and makes real cross-UID socket attempts with (1) same signed grant replay and (2) correctly HMAC-signed grant whose short expiration has elapsed. Both must be denied, and ledger consumption count must remain exactly one.
- Signed socket requires the actual trusted UID primary GID. This is an opt-in isolated acceptance harness; production service unchanged.
- VPS re-test pending. Important remaining: supervised long-running broker deployment, trusted service live integration, key rotation and worker-group isolation proof. Do not claim production-ready or enable autonomous tools.

## Production integration scaffold (2026-11-07)
- VPS confirmed 188/188 PASS and real multiprocess approval -> systemd, worker denial, replay and expired signed grant denial PASS. Service active.
- New `agency/supervised_broker.py`: opt-in long-running root listener, signed-only, peer UID enforcement via handler, fresh key read per request, bounded audit event on denial; example unit in `deploy/hermes-signed-broker.service.example` (NOT installed or enabled).
- New `agency/broker_key_rotation.py`: operator-only atomic 64-byte HMAC key replacement, old grants invalidated immediately; rotate only after quiescing broker and issuer. No online dual-key overlap. Three additional unit gates; expected 191 tests, VPS not yet verified.
- CRITICAL NOT COMPLETE: live trusted service still has no broker-grant issuance endpoint; do not expose issuance to worker. Example unit requires real systemd-run acceptance with its hardening settings; no production listener deployment, no key lifecycle acceptance and no integration with running service. Never enable production agent tools. Next milestone: trusted-side operator-authorized grant transport, supervised broker real E2E and rotation acceptance with separate test service, then controlled deployment.

## Trusted broker production adapter (2026-11-07)
- User VPS verified 191/191 PASS and real multiprocess broker positive/negative acceptance PASS; production service remains active.
- Added `agency/trusted_broker_adapter.py`: trusted-process-only adapter consumes a real prior approval with existing worker credential and lease, loads root:trusted 0640 HMAC key under non-root trusted identity, submits to signed-only broker socket. It deliberately exposes no remote worker endpoint and cannot self-approve.
- Added adapter security tests and an isolated root-only HMAC rotation signature invalidation test (skipped unless root with non-root primary GID). Expected unit count 194, depending on environment. VPS not yet verified.
- Production integration NOT complete: live trusted service does not invoke adapter yet; supervised broker systemd unit not deployed/tested; real end-to-end supervised broker plus rotation across sockets not yet tested. Avoid enabling service or autonomous tools before full proof.

## Opt-in supervised integration acceptance package (2026-11-07)
- Last VPS result: 194 tests OK (1 skipped), isolated multiprocess positive/negative PASS, existing production service active.
- Added `agency/supervised_integration_client.py`: genuine trusted-UID process creates task, lease, approver decision and submits fixed noop via trusted broker adapter. No worker-facing approval endpoint.
- Added `deploy/test_supervised_integration.sh`: ROOT-only opt-in isolated test; starts transient broker with systemd-run, checks socket root:trusted 0660, worker denial, trusted adapter -> real sandbox, atomic key rotation, fresh grant under new key, and two completed ledger entries. Stops transient unit and removes temporary test state on exit. Does NOT install/enable production service or modify its state.
- Test harness uses ProtectHome=no solely to load a temporary code copy from /tmp, NOT the production unit security configuration. Therefore passing it does NOT certify the production example unit's hardening or live running hermes-agency.service integration.
- IMPORTANT outstanding: test rejection of an unconsumed OLD signed grant after rotation (not yet covered by this script); real production trusted service transport integration; deployment unit hardening compatibility; dedicated key lifecycle/quiescence and operational rollback. Do not enable autonomous agent execution.
- VPS verification pending; execute `bash deploy/test_supervised_integration.sh` only after regression acceptance and review of root-only transient unit test.

## VPS supervised startup failure and correction (2026-11-07)
- VPS reported `ModuleNotFoundError: No module named 'agency'` in transient systemd unit; production hermes-agency.service remained active. This is an import-path startup failure, not a broker authorization result.
- Fixed isolated test script to pass explicit systemd working directory and PYTHONPATH to broker and both non-root trusted client invocations. Re-run pending; no claim of successful supervised E2E until VPS confirms.

## Verified VPS supervised acceptance (2026-11-07)
- Operator VPS reported `bash deploy/test_supervised_integration.sh` EXIT_CODE=0: two `supervised_trusted_adapter_to_systemd=PASS`, `supervised_systemd=PASS worker_denied=PASS key_rotated_new_grants=PASS ledger=PASS`.
- Existing `hermes-agency.service` remained active. This proves transient systemd supervised broker and isolated trusted UID client E2E, not live production trusted-service integration.
- Remaining gates: explicitly reject pre-rotation unused signed grant after key rotation, verify production unit hardening, and connect real running trusted service via authenticated operator-only path; no production activation yet.

## Production broker unit static audit (2026-11-07)
- Added `agency/broker_unit_audit.py` and 2 tests: checks exact opt-in production example's security-critical unit directives, bounded writable paths and signed-only entrypoint; negative test rejects weakened ProtectSystem. Expected suite 196 tests, VPS pending.
- This is STATIC configuration verification, NOT systemd execution with the production unit. A systemd-analyze verify and live test of production-equivalent hardening are still required.
- No live trusted service code or worker protocol changed. Operator-only live service integration and pre-rotation unused grant rejection are NOT yet implemented or proven. Do not activate production broker.

## Broker production hardening iteration (2026-11-07)
- Hardened opt-in `deploy/hermes-signed-broker.service.example` with kernel, control group, device, SUID/SGID, personality, realtime and syscall architecture restrictions. Updated static audit to require all new directives.
- VPS verification and production-equivalent runtime acceptance are pending. The existing transient acceptance harness does not use this unit's full hardening and cannot certify compatibility.
- Unused pre-rotation grant rejection test and authenticated integration into the running trusted service are still pending; isolated acceptance's self-issued operator credential is NOT a substitute for a real authenticated operator.
- No live service restart, broker deployment, or worker privilege changes performed.

## Runtime security acceptance expansion (2026-11-07)
- Added isolated trusted-client `--prepare-path` for creating a genuinely approved but **unsubmitted** signed grant; the supervised harness rotates the HMAC key, attempts the still-unexpired old grant, asserts rejection and no new ledger consumption, then executes a fresh post-rotation grant. VPS result pending.
- The transient supervised systemd test now enables kernel/device/control-group/personality/SUID/realtime/syscall-architecture restrictions from the hardened production template. It deliberately uses `PrivateTmp=no`, `ProtectHome=no`, and temporary test-specific ReadWritePaths/WorkingDirectory, so this is **not** full production-unit equivalence.
- Added `TrustedAgentExecution.execute_operator_approved_job` as an **in-process only** adapter requiring an already approved request, worker credential and lease; existing worker-facing stage protocol is unchanged. This is **not yet connected** to the running `hermes-agency.service` or to an external authenticated operator entrypoint; deployment and live E2E still pending.
- No persistent broker installed, no live trusted service restarted, no worker permission expanded.

## VPS verified runtime acceptance (2026-11-07)
- VPS operator reported `Ran 196 tests ... OK (skipped=1)` and `RUNTIME_EXIT_CODE=0` for `deploy/test_supervised_integration.sh`.
- Runtime output: `unused_signed_grant_prepared=PASS`, `unused_pre_rotation_grant_rejected=PASS`, `rejected_grant_no_execution=PASS`, two `supervised_trusted_adapter_to_systemd=PASS`, and `supervised_systemd=PASS worker_denied=PASS key_rotated_new_grants=PASS ledger=PASS`.
- `hermes-agency.service` remained active. This validates the isolated hardened transient unit and key-rotation negative test, not full production unit equivalence or the live authenticated operator integration.
- Next gate: inspect actual operator authentication/approval infrastructure and connect it to the running trusted process without worker-accessible broker issuance or production state changes until approved.

## Authenticated operator integration design (2026-11-07)
- Inspected live service implementation: `single_vps_service.py` / `service_lifecycle.py` expose only worker stage IPC, and `operator_auth.py` contains offline-provisioned scrypt verifier `LocalOperatorGate`.
- Added `TrustedAgentExecution.approve_operator_request` to authenticate a local operator secret via `LocalOperatorGate` before calling the existing approval service. In-process method only; never added to worker IPC.
- This does NOT yet establish an operator-only transport, rate limiting, credential provision on VPS, live service integration or production broker activation. No claims of completed live end-to-end authentication; runtime tests pending.

## VPS operator boundary follow-up (2026-11-07)
- VPS operator reported 196 unit tests OK (1 skipped) on prior branch head; `hermes-agency.service` remained `active`. These tests precede new regression tests below.
- Added two regression tests in `tests/test_trusted_execution.py`: wrong operator secret cannot advance pending approval, and worker-role credential cannot substitute for operator secret. The correct secret exercises the existing LocalOperatorGate-to-TrustedApprovalService approve path.
- No live operator-only IPC socket or authenticated integration with the running service exists yet; only in-process trusted boundary is tested. These new tests require VPS/CI execution before pass can be claimed.
- No changes to production service, deployed broker, or worker-facing protocol.

## Authenticated local operator sidecar implementation (2026-11-07)
- VPS operator verified the previous authentication regression tests: `Ran 198 tests ... OK (skipped=1)`, `TEST_EXIT_CODE=0`, and `hermes-agency.service=active`. These results predate the operator-sidecar changes below.
- Implemented strict, bounded operator-only local Unix socket protocol (`agency/operator_control.py`), kernel `SO_PEERCRED` UID-0 gate **before** request body read, scrypt `LocalOperatorGate` authentication, approval and existing signed broker adapter. No worker-facing endpoint additions.
- Security review found a critical *group-sharing risk* in the first dual-socket proposal: a worker-accessible transport group must not own/read the broker signing key. **Restored `single_vps_service.py` and `service_lifecycle.py` to their existing unchanged worker behavior** and moved the operator listener into standalone `agency/operator_service.py`, running as the same non-root trusted UID but with its own private key-reading effective GID, explicitly denying workers in that group. Rejects root-effective group and root worker identity.
- Added interactive secret-free-argv `agency/operator_client.py`, trusted-only offline scrypt-verifier provisioner `agency/operator_provision.py`, and `docs/OPERATOR_CONTROL.md`.
- Expanded `deploy/test_supervised_integration.sh` to spawn an **isolated** transient sidecar, verify worker operator-socket denial, reject wrong secret without changing pending approval or broker ledger, and verify correct root operator approval -> trusted SQLite -> signed broker -> systemd `noop` completion. The previous HMAC rotation checks remain intact.
- Added negative/schema/group separation tests in `tests/test_operator_control.py` and `tests/test_operator_service_options.py`.
- GitHub Actions run 42321290737 independently reported success at commit `00d608ee65db19ea30f7910667b8d0d4126af34c` (unit job success). The latest added unit tests and the expanded **VPS runtime acceptance are not yet confirmed**; no claim of production equivalence.
- **Production status:** no code deployed to `/opt/hermes-agency`, no production service restart, no persistent broker/sidecar installed, no production operator verifier or secret created. Existing `hermes-agency.service` preserved.
- Next gate: inspect latest CI, run `bash deploy/test_supervised_integration.sh` in development checkout under root with isolated fixtures; on failures patch the minimum issue. After PASS, separately review live UID/GID, key access, unit hardening, provisioning and rollback before any production deployment.


## Operator sidecar isolated VPS acceptance verified (2026-11-07)
- VPS development checkout confirmed `git pull --ff-only origin development/foundation` already up to date at the existing milestone; `python3 -m unittest discover -s tests -q` ran **218 tests, OK (skipped=1)**, exit 0. Two argparse usage messages were expected negative-path tests, not failures.
- `bash -n deploy/test_supervised_integration.sh` exited 0.
- Actual root-run isolated supervised acceptance exited **0**: two trusted adapter-to-systemd successes; unused pre-rotation grant rejected with no ledger execution; worker denied operator socket; invalid operator secret denied with pending approval and ledger unchanged; authenticated operator approval consumed and executed fixed job through signed broker; final ledger had exactly three completed entries.
- `systemctl is-active hermes-agency.service` returned `active` after the test. GitHub Actions run 42321329650 unit job concluded success (218 tests reported in prior handoff).
- **Scope of proof:** transient isolated broker/operator units with temporary keys, database and relaxed test paths. This does NOT certify production-equivalent unit hardening, production key/UID/GID permissions, or live deployment. No production changes authorized or performed.
- **Next gate:** perform read-only host inventory of `systemctl cat/show` for existing service, `systemd-analyze verify` on opt-in example units, user/group membership and path ownership/modes without printing secret contents. Check broker capability and writable-path requirements; design isolated production-equivalent runtime test and rollback. Obtain explicit authorization before any production install, credential provisioning, permission change or restart.


## VPS read-only production layout and systemd template verification (2026-11-07)
- Operator ran `systemd-analyze verify` on a temporary `.service` copy of `deploy/hermes-signed-broker.service.example`: **exit 0**. Previous `agency.broker_unit_audit` static check also returned PASS. Neither result proves a production sandbox start.
- `hermes-agency.service` has `WorkingDirectory=/opt/hermes-agency`; `ExecStart` was truncated by terminal output and must not be assumed in full.
- Trusted state `/var/lib/hermes-agency` is `0700 hermes-trusted:hermes-trusted`; worker transport directory `/run/hermes-agency` is `0710 hermes-trusted:hermes-agents`. `hermes-trusted` primary GID 986 and worker primary GID 985 are distinct; both belong to shared `hermes-agents` GID 987. Broker signing key must never be group-readable by GID 987.
- `/etc/hermes-broker`, `/var/lib/hermes-broker`, and `/run/hermes-broker` do not exist. This is expected before opt-in provisioning; **do not** create them without explicit approval.
- Next read-only gate: inspect complete existing service command (`systemctl show --value -p ExecStart` without truncation), root-owned application code and trusted credential path metadata only, and installed systemd version. Review sandbox capabilities and unit startup dependencies. No production installation, key provisioning, chmod/chown or restart authorized.


## Production service command and trusted state metadata verified (2026-11-07)
- VPS operator confirmed systemd 255 (Ubuntu 255.4-1ubuntu8.18). Current `hermes-agency.service` ExecStart is `/usr/bin/python3 -m agency.single_vps_service --forever --socket /run/hermes-agency/trusted.sock --state-dir /var/lib/hermes-agency --database /var/lib/hermes-agency/agency.db --key-dir /var/lib/hermes-agency/keys --client-gid 987 --allow-uid 995 --secret-file /var/lib/hermes-agency/keys/signing.key`.
- `/opt/hermes-agency` and `/opt/hermes-agency/agency` are `0755 root:root`; `/var/lib/hermes-agency` and `/var/lib/hermes-agency/keys` are `0700 hermes-trusted:hermes-trusted`; `agency.db` and `keys/signing.key` are `0600 hermes-trusted:hermes-trusted`. This matches the intended trusted-state isolation. Worker transport uses shared GID 987, which must never be used for broker key group-read.
- The existing service is the original `agency.single_vps_service`; no production broker/operator sidecar directories or units have been provisioned. The installed application revision was **not** independently checked against development; do not assume it contains operator-sidecar code.
- Next gate: review production-equivalent sandbox dependencies, secure broker key provisioning, operator socket directory lifecycle, runtime path access, and rollback. Require separate explicit approval for any production filesystem/service mutation. Do not treat systemd static verification as production-equivalent runtime acceptance.


## Production-like isolated acceptance harness and deployment plan (2026-11-07)
- Added `deploy/test_production_equivalent_acceptance.sh`, derived from the previously VPS-passing isolated integration harness. Uses temporary `/run` fixtures and transient units with `ProtectHome=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, bounded broker capabilities and additional operator sandbox restrictions, while retaining the existing negative/positive acceptance checks. No production paths, keys, units or services are modified intentionally. **New harness has NOT yet been executed on VPS or confirmed passing.**
- Added `docs/PRODUCTION_ACCEPTANCE_AND_DEPLOYMENT.md` with explicit gates: isolated runtime test, read-only revision/path inventory, separate broker-key/verifier/runtime-directory provisioning design, and rollback. Production activation is explicitly withheld pending tests and separate user approval.
- Next action: VPS operator runs `bash -n deploy/test_production_equivalent_acceptance.sh` and `bash deploy/test_production_equivalent_acceptance.sh`, reports exit codes and current service status. On failure inspect transient journal and patch minimally; never weaken hardening solely to pass. Do not install or activate production broker/sidecar.


## VPS production-like hardened runtime acceptance verified (2026-11-07)
- VPS operator pulled branch at `3c4b579` and ran `bash -n deploy/test_production_equivalent_acceptance.sh`: **SYNTAX_EXIT_CODE=0**.
- Ran the new isolated `/run` fixture and transient systemd broker/operator harness with hardened settings: **HARDENED_RUNTIME_EXIT_CODE=0**. Output confirmed two trusted adapter-to-systemd PASS checks, stale unused HMAC grant rejected without ledger execution, worker operator-socket denial, wrong operator secret denial, authenticated operator-to-systemd PASS, and final ledger PASS.
- Existing `hermes-agency.service` remained **active** after acceptance. No production broker/operator units or keys were installed or provisioned by the test.
- **Gate A is complete:** production-like isolated runtime acceptance. This is not final production unit equivalence, production provisioning validation, or activation approval.
- **Next gate:** finalize production unit files and read-only review of installed code revision, runtime directory lifecycle, key and verifier provisioning, sandbox compatibility, backup/rollback, and explicit authorization boundaries. Do not install/enable/restart production services without a separate user approval.


## Production checkout revision inspection (2026-11-07)
- VPS operator pulled development branch at `3791ea759bdbc8c90fafc2fc822506614ace850d`; `git -C /opt/hermes-agency rev-parse HEAD` reported `not a git repository`. Production appears to be a file deployment without Git metadata; installed code revision is **unknown**, not assumed current.
- Existing `hermes-agency.service` remained active. Next: compare SHA-256 of selected security-critical Python files in development versus installed production, without exposing contents or changing files. Do not infer overall tree equivalence from a small sample.


## Production file hash comparison (2026-11-07)
- VPS development checkout at `57dc778`; `/opt/hermes-agency` is not a Git checkout. SHA-256 hashes of `agency/single_vps_service.py`, `agency/service_lifecycle.py`, and `agency/private_state.py` match development exactly.
- `agency/trusted_execution.py` differs: development `61f66b9878d63b164318afc716382fb59df1d01b194aa483a1e781d7531135ff`, production `ab1dc7259b80aca85e7fea60a202b71446e4fd5363ab310d6c57eb62b10520f6`.
- `agency/supervised_broker.py`, `agency/operator_service.py`, and `agency/operator_control.py` are absent from production. Main service remains `active`.
- **Deployment blocker:** complete dependency inventory and compatibility check needed before any file copy. Preserve production worker behavior and prepare atomic/rollback-safe deployment; no production changes authorized. Update production plan accordingly.


## Complete production Python package inventory (2026-11-07)
- VPS operator compared all `.py` files under development `/root/Hermes-Agency/agency` versus production `/opt/hermes-agency/agency`: **27 identical, 1 different, 22 missing, 0 production-only**. Existing `hermes-agency.service` remained `active`.
- Sole differing file: `trusted_execution.py`. Missing development modules: `adaptive_sandbox.py`, `broker_grants.py`, `broker_key_rotation.py`, `broker_unit_audit.py`, `full_broker_acceptance.py`, `isolated_jobs.py`, `linux_sandbox.py`, `operator_client.py`, `operator_control.py`, `operator_provision.py`, `operator_service.py`, `sandbox_preflight.py`, `sandbox_validation.py`, `signed_broker_service.py`, `supervised_broker.py`, `supervised_integration_client.py`, `systemd_acceptance.py`, `systemd_broker.py`, `systemd_broker_e2e.py`, `systemd_jobs.py`, `trusted_broker_adapter.py`, `trusted_job_admission.py`.
- Source review confirms development `trusted_execution.py` imports new `trusted_broker_adapter.py` and `operator_auth.py`; copying it alone would break if the adapter is absent. New operator/broker runtime further depends on `broker_grants.py`, `signed_broker_service.py`, `systemd_broker.py`, `systemd_jobs.py` and existing trusted modules. Not all missing modules are required in production; several are acceptance/test utilities.
- **No production copy or restart performed.** Next: create a minimal explicit runtime-module manifest and test import compatibility in a disposable staging tree, then design final units and rollback. Do not blindly copy all 22 modules or replace the live trusted execution file.


## Development runtime import smoke test (2026-11-07)
- VPS operator pulled `dfef5f3` and imported 12 modules successfully: `trusted_execution`, `trusted_broker_adapter`, `broker_grants`, `signed_broker_service`, `supervised_broker`, `systemd_broker`, `systemd_jobs`, `operator_auth`, `operator_control`, `operator_service`, `operator_provision`, `operator_client` (all under `agency`).
- Existing production `hermes-agency.service` remained `active`.
- Scope: imports from the **development checkout**, not from an isolated staging tree or installed production. No claim of full production compatibility or final deployment readiness.
- Next: test an explicit minimal runtime manifest in a disposable staging tree based on the installed production package, including import checks, relevant tests and no production changes; then review final unit files and provisioning/rollback before requesting activation approval.


## Minimal production-based staging import test prepared (2026-11-07)
- VPS AST output identified relative imports for the broker/operator runtime; no parser errors despite duplicated terminal echo. Existing baseline has 27 matching Python files, one differing and 22 missing.
- Added `deploy/test_runtime_staging_imports.sh`: creates throwaway `/tmp` package, copies only top-level `.py` source files from installed production (no keys/DB), overlays 11 explicitly listed runtime/operator files from development including `trusted_execution.py`, and uses isolated Python (`-I`) to assert 14 critical modules import **from staging only**. Cleans up temporary package on exit. Does not change production.
- **Test has not been run on VPS yet.** Next: run `bash -n deploy/test_runtime_staging_imports.sh` and `bash deploy/test_runtime_staging_imports.sh`, then report exit code and main service status. An import PASS is not a production execution or final sandbox acceptance.


## VPS production-based minimal staging import acceptance (2026-11-07)
- Operator ran `bash -n deploy/test_runtime_staging_imports.sh`: `SYNTAX_EXIT_CODE=0`.
- Disposable package built from installed production Python sources plus the explicit 11-file runtime overlay imported all 14 selected modules successfully (`STAGING_IMPORT_EXIT_CODE=0`, `STAGING_EXIT_CODE=0`). Script reported `PRODUCTION_UNCHANGED=YES`; existing `hermes-agency.service` remained `active`.
- This validates module import resolution only; does not establish full runtime/ABI compatibility, complete production unit hardening, data migration safety or production activation approval.
- Next: finalize optional broker/operator systemd units, secure runtime-directory lifecycle and provisioning/rollback runbook; review without installing, provisioning credentials or restarting production. Explicit approval required for activation.


## Deployment preparation templates and rollback runbook (2026-11-07)
- Added **opt-in, uninstalled** `deploy/hermes-operator-sidecar.service.example` (trusted UID/private GID, root-only operator socket, protected state, hardened systemd sandbox) and `deploy/hermes-optional-runtime.tmpfiles.example` (reboot-safe creation of isolated broker/operator socket directories). Existing broker template remains `deploy/hermes-signed-broker.service.example`.
- Added `docs/PRODUCTION_PROVISIONING_RUNBOOK.md`: prerequisites, minimal 11-file runtime overlay, one-time root broker key and private ledger provisioning, interactive trusted-UID scrypt operator verifier, tmpfiles and unit installation order, controlled validation and rollback that preserves the live service and databases.
- **These are preparation artifacts only.** No production filesystem or service modifications, secret provisioning or activation performed. Templates still require VPS `systemd-analyze verify`, private group and path review, and final approval. Do not claim deployment readiness until checks pass.
- Next: VPS operator performs **read-only** static validation of both templates and tmpfiles, including systemd syntax, without copying them to `/etc` or starting units. Address any findings in development branch, then request separate explicit approval for actual provisioning/activation.


## VPS static deployment template verification (2026-11-07)
- User ran `systemd-analyze verify` on temporary `.service` copies of both broker and operator sidecar units: `SYSTEMD_VERIFY_EXIT_CODE=0`.
- Broker static hardening audit: `production_unit_static_hardening=PASS`, `BROKER_AUDIT_EXIT_CODE=0`.
- `systemd-tmpfiles --cat-config deploy/hermes-optional-runtime.tmpfiles.example` displayed global tmpfiles configuration (output truncated at lines 1–32), not conclusive evidence of Hermes-specific entries. `TMPFILES_READ_EXIT_CODE` and final production service status were not visible in the provided output; **do not infer their values**.
- Next: validate the exact two Hermes tmpfiles entries without running `--create` or `--remove`, confirm exit code and service state. No production activation or provisioning authorized.


## Hermes tmpfiles static validation complete (2026-11-07)
- VPS operator ran exact read-only parser comparison for `deploy/hermes-optional-runtime.tmpfiles.example`: `HERMES_TMPFILES_STATIC_CHECK=PASS`, `TMPFILES_CHECK_EXIT_CODE=0`.
- Existing `hermes-agency.service` was `active` after the check. Prior broker/sidecar `systemd-analyze verify` and broker static hardening audit were PASS; minimal production-based staging imports 14/14 PASS; isolated hardened runtime acceptance previously PASS.
- **Deployment preparation static gates completed**, but optional units/tmpfiles not installed, secrets/verifier/ledger not provisioned, live production path permissions and service activation not validated. Explicit authorization and controlled backup/rollback required before production modification.


## Controlled production deployment authorization (2026-11-07)
- User explicitly authorized deployment of the **optional signed broker and trusted operator sidecar** to production, preserving the existing `hermes-agency.service` and keeping general agent execution disabled. This is not authorization to restart the main service, widen agent privileges, replace credentials, or delete state.
- Execution is gated: first collect read-only host preflight (users/groups, exact paths, filesystem/mount status, running unit, Python package permissions, free space, service account group separation), then verify backup/rollback feasibility and safe code overlay before provisioning or installing optional units.
- No VPS access via GitHub connector; assistant cannot assert host modifications. Operator must execute approved reviewed commands and return outputs. Never print secrets, copy SQLite while live without consistent snapshot, or start optional units before path/security checks.


## Production read-only host preflight PASS (2026-11-07)
- Live `hermes-agency.service` active; trusted uid:gid 997:986 and worker 995:985; both have shared transport group 987 but worker is not in trusted private group 986.
- Trusted state and key dirs `0700` trusted:trusted; SQLite and credential signing key `0600` trusted:trusted. `/opt/hermes-agency` and `/opt/hermes-agency/agency` `0755` root:root; production `trusted_execution.py` `0644` root:root.
- Root filesystem 29G, 22G used, 6.7G available, 77% used; inode use 13%. Optional broker and operator units `not-found`, `/etc/hermes-broker`, `/var/lib/hermes-broker`, `/run/hermes-broker`, `/run/hermes-operator` absent.
- Preflight passes **observed ownership/group/layout gates only**. No backup, file replacement, secret provisioning, optional unit installation or activation has occurred. Next gate: plan consistent SQLite snapshot and verified rollback archive, avoiding disclosure of credentials and interruption to running service.


## Production backup completed and verified (2026-11-07)
- User executed approved root-only backup at `/root/hermes-deployment-backups/20261107T013007Z` (directory `0700 root:root`).
- Backup contains `production-agency.tar.gz` (original installed agency code), `trusted-keys.tar.gz` (sensitive credentials), consistent SQLite Backup API snapshot `agency.db` (integrity check PASS), and `SHA256SUMS` (all three files OK). Archives validated; production main service remained `active`.
- Treat backups as sensitive and do not transmit secrets. Preserve live database during rollback rather than restoring snapshot by default. Next gate: preflight exact 11-file runtime overlay and rollback strategy before writing `/opt/hermes-agency`; do not replace unrelated modules.


## Production broker key and ledger provisioned (2026-11-07)
- User executed root-only provisioning after identity and existing-path checks. `/etc/hermes-broker` `0710 root:hermes-trusted`, `/etc/hermes-broker/signing.key` `0640 root:hermes-trusted` (64 raw bytes), `/var/lib/hermes-broker` `0700 root:root`, `/var/lib/hermes-broker/ledger.sqlite` `0600 root:root`.
- Output `BROKER_PROVISIONING=PASS`, `BROKER_KEY_SIZE=PASS`; main `hermes-agency.service` remains `active`.
- Broker and operator units not yet installed or started. Never re-run exclusive provisioning blindly, rotate keys, or expose credentials. Next gate: interactive operator verifier provisioning under trusted private UID/GID, then opt-in tmpfiles and systemd unit installation and validation.


## Production operator verifier provisioning (2026-11-07)
- User executed `runuser -u hermes-trusted -g hermes-trusted -- /usr/bin/python3 -m agency.operator_provision --path /var/lib/hermes-agency/keys/operator-verifier.json --identity operator` from `/opt/hermes-agency`; interactive command returned `operator_verifier_provisioned=PASS`.
- Operator secret was not disclosed. File mode/ownership and main service status still require separate read-only verification before optional unit installation. Do not repeat exclusive provisioning or reveal secret.


## Production operator and broker credential permission checks PASS (2026-11-07)
- VPS verified operator verifier regular non-symlink `0600 hermes-trusted:hermes-trusted` (`OPERATOR_VERIFIER_PERMISSIONS=PASS`), broker signing key `0640 root:hermes-trusted` and 64-byte length (`BROKER_CREDENTIAL=PASS`), main service `active` (`MAIN_SERVICE=ACTIVE`).
- Broker and operator credential provisioning completed. Next: install opt-in tmpfiles and service unit definitions in separate, controlled stages, verify without starting, then explicit runtime security checks before enablement. No service activation reported yet.


## Production tmpfiles deployment PASS (2026-11-07)
- User installed `/etc/tmpfiles.d/hermes-optional-runtime.conf` from the repository template and ran `systemd-tmpfiles --create`.
- Verified `/run/hermes-broker` `0710 root:hermes-trusted`, `/run/hermes-operator` `0700 hermes-trusted:hermes-trusted`, optional broker and operator services inactive, main `hermes-agency.service` active; output `TMPFILES_DEPLOYMENT=PASS`.
- Next: install and statically verify optional systemd unit files without starting or enabling them, then validate staged activation and negative access tests.


## Production optional systemd units installed, inactive (2026-11-07)
- User installed broker and operator unit templates unchanged to `/etc/systemd/system/hermes-signed-broker.service` and `/etc/systemd/system/hermes-operator-sidecar.service`; `cmp` and `systemd-analyze verify` succeeded, followed by `systemctl daemon-reload`.
- Both optional units verified `disabled` and `inactive`; main `hermes-agency.service` active; `SYSTEMD_UNIT_INSTALLATION=PASS`.
- Next: start broker only under explicit controlled test, verify root process and socket permissions and absence of startup errors, then operator sidecar and negative-access tests. Do not enable at boot until full production acceptance.


## Production runtime regression observed (2026-11-07)
- Earlier runtime overlay verification passed (11 installed and imported), but broker startup entered restart loop (`No module named agency.supervised_broker`, `NRestarts=31`). User stopped broker; main service remains active, broker/operator inactive.
- Read-only inventory now finds `trusted_execution.py` present but **all 10 optional runtime modules missing** from `/opt/hermes-agency/agency`; directory and `trusted_execution.py` mtimes around `2026-11-07 01:37:52 UTC`. Cause of removal not yet established. Do not claim environment/PYTHONPATH is cause; direct import returned NOT_FOUND.
- Next: investigate deployment/cleanup processes and compare `trusted_execution.py` with repository and backup before controlled reinstallation. Do not restart main service, rerun credential provisioning, or activate optional units until root cause and runtime integrity are checked.


## Runtime recovery verification (2026-11-07)
- User verified `SOURCE_MODULES=PASS`, three backup SHA256 checks OK, and main/broker/operator states active/inactive/inactive.
- After running the recovery procedure, a separate-shell production import check returned `MODULE_PERSISTENCE=PASS` for `agency.supervised_broker` and `agency.operator_service`; module inventory again shows optional broker/operator modules present. Main service remained active, optional services inactive.
- Recovery script's own `RUNTIME_RECOVERY=PASS` output was not supplied, so do not assert that specific marker. Next step: one-shot controlled broker startup with `Restart=no` runtime override, verify socket/service and journal, then remove override. Do not enable at boot until end-to-end signed-grant and operator checks pass.


## Production broker listener acceptance (2026-11-07 01:46 UTC)
- With a temporary `/run/systemd/system/hermes-signed-broker.service.d/90-startup-test.conf` override `Restart=no`, broker starts successfully: `ActiveState=active`, `SubState=running`, `MainPID=994337`, `NRestarts=0`, root process.
- `/run/hermes-broker/broker.sock` exists, mode 0660, owner root:hermes-trusted; parent `/run/hermes-broker` mode 0710; `ss -xlpn` confirms broker process listening. Main Hermes remains active. This verifies startup/listener only, not signed grant security or operator sidecar.
- Next: test unauthorized peer rejection and authorized signed request in controlled scope, verify ledger/DB and no unauthorized systemd jobs, then operator sidecar. Keep `Restart=no` and optional units disabled until end-to-end acceptance.


## Production worker socket boundary (2026-11-07)
- Verified identities: hermes-worker UID 995/GID 985 (groups 985,987); hermes-trusted UID 997/GID 986 (groups 986,987). Broker parent `/run/hermes-broker` root:hermes-trusted 0710; socket root:hermes-trusted 0660.
- Actual `runuser -u hermes-worker` socket connect returned `PermissionError`, `WORKER_ACCESS_DENIED=PASS`. Broker and main service remain active.
- Next: safely test malformed/unsigned trusted-UID request rejection, then operator sidecar and valid signed grant with narrow authorized fixture. Keep optional services disabled at boot and broker temporary `Restart=no` during testing.


## Production unsigned request rejection (2026-11-07)
- As `hermes-trusted`, connection to `/run/hermes-broker/broker.sock` succeeded. Sending `{"grant":{}}\n` returned EOF (`b''`); broker journal logged `{"broker":"denied","reason":"PermissionError"}`. Broker and main service remained active.
- This validates one malformed/unsigned request rejection, not replay/expiry/forgery or valid signed grant acceptance. Next test operator sidecar startup and socket identity under temporary `Restart=no`, then explicit controlled signed grant end-to-end.


## Production operator sidecar startup acceptance (2026-11-07 01:49 UTC)
- Production operator state/DB/key/verifier metadata: trusted-owned private dirs 0700, DB/verifier 0600; broker key 0640 root:hermes-trusted and 64 bytes. Unit uses `User=hermes-trusted`, `Group=hermes-trusted`.
- Temporary `/run/systemd/system/hermes-operator-sidecar.service.d/90-startup-test.conf` sets `Restart=no`. Operator started successfully PID 995055, `ActiveState=active`, `SubState=running`, `NRestarts=0`; `/run/hermes-operator/operator.sock` 0600 hermes-trusted:hermes-trusted, listening. Broker and main service also active.
- Next: verify operator socket rejects worker/root unauthorized protocol, then controlled valid authentication and signed-grant ledger acceptance. Keep both optional units disabled at boot, `Restart=no` until production acceptance.


## Production worker-to-operator isolation (2026-11-07)
- `runuser -u hermes-worker` direct connect to `/run/hermes-operator/operator.sock` returned `PermissionError`, `WORKER_OPERATOR_ACCESS_DENIED=PASS`; main, broker, and operator remained active.
- Verified both private sockets reject worker, and broker rejects an unsigned trusted-UID payload. Next: protocol authentication negative tests and controlled signed-grant transaction/replay checks. Optional units remain disabled at boot and `Restart=no` runtime overrides remain in place.


## Production operator invalid-credential denial (2026-11-07)
- Root client sent `approve` request to operator socket with nonexistent approval ID and all-zero 64-hex secret. Operator returned `{"status":"denied"}`, `INVALID_CREDENTIAL_REJECTED=PASS`. Main, broker, and operator remained active.
- This is one negative authentication test, not proof of valid credential acceptance or signed-grant execution. Next: review fixed job allowlist and grant issuance before selecting harmless production acceptance test. No auto-enable yet.


## Signed broker SQLite fencing candidate (2026-11-07)
- Production SQLite uses journal_mode=delete, trusted database parent is trusted-owned 0700, database 0600. Broker ProtectSystem=strict currently permits writes only under broker runtime/ledger directories; this conflicts with execute_signed_grant's BEGIN IMMEDIATE on trusted SQLite.
- Added review-only candidate `deployment/systemd/hermes-signed-broker.service.d/20-trusted-db-sqlite.conf`: grants ReadWritePaths to trusted database directory while making its keys directory inaccessible. **Not installed or activated in production.** This broadens root broker write access to the trusted DB and requires explicit security acceptance; a narrower broker/trusted-UID IPC redesign remains preferable for long-term least privilege.
- Before deployment, validate sandbox mount behavior, SQLite lock fencing, key inaccessibility, and no regression to main service. Both optional units remain disabled at boot; temporary Restart=no overrides remain.


## Isolated systemd/SQLite candidate acceptance (2026-11-07)
- Operator ran transient systemd test with dummy SQLite and dummy key under `/run`, `ProtectSystem=strict`, `ReadWritePaths=<temporary dir>`, `InaccessiblePaths=<temporary dir>/keys`, `NoNewPrivileges=yes`, and bounded capabilities. Observed `KEY_ISOLATION=PASS`, `SQLITE_BEGIN_IMMEDIATE=PASS`, `CONCURRENT_WRITER_BLOCKED=PASS`, `SQLITE_COMMIT=PASS`, `ISOLATED_SANDBOX_TEST=PASS`, exit 0.
- This confirms isolated mount masking and SQLite writer exclusion only; does not validate production key paths, actual broker signed-grant, replay handling, or live lease fencing. No production unit modified. Source review: `systemd_broker.execute_signed_grant` locks trusted DB with `BEGIN IMMEDIATE` and rolls back after job, while `SecureAgencyStore` uses `BEGIN IMMEDIATE` for claim/transition. This is the intended contention boundary, not yet an E2E acceptance result.
- Next: add regression tests for lease-revocation contention and replay, validate production-equivalent sandbox in isolated fixture, then explicitly review narrow production rollout. Longer term move lease fencing into trusted UID process to avoid granting root broker broad trusted DB write access.


## Production non-destructive acceptance (2026-11-07 01:59:42 UTC)
- Operator executed /root/hermes-full-acceptance.sh; report /root/hermes-acceptance-20261107T015942Z.log.
- Repository checkout at 82acc07 (older than latest branch documentation commits); git status --short empty. Unit tests: 218 OK, 1 skipped; expected CLI parser negative-path stderr emitted during tests.
- Main, signed broker, and operator sidecar services all active. Broker and operator optional services disabled at boot, Restart=no, NRestarts=0.
- Broker socket 0660 root:hermes-trusted, operator socket 0600 hermes-trusted:hermes-trusted. Worker denied both socket connections. Invalid operator credential denied. Isolated SQLite BEGIN IMMEDIATE competing-writer exclusion and commit passed.
- Acceptance summary: FAILURES=0, FULL_NONDESTRUCTIVE_ACCEPTANCE=PASS, ACCEPTANCE_EXIT_CODE=0.
- Scope limitation: no real positive approved signed-grant, replay or expired-grant, revocation race, real systemd fixed job, or audit ledger E2E tested. No production restart, DB mutation, or boot-policy changes performed by this acceptance script. Production readiness is NOT yet approved.


## Targeted broker integration suite (operator evidence, 2026-11-07)
- On VPS checkout 82acc07, operator ran 14 explicit unittest modules for broker grants, operator authentication, systemd restrictions, trusted adapter, and trusted broker socket.
- Result: Ran 77 tests in 0.890s, OK (skipped=1); zero failures. Expected CLI argparse negative-test errors appeared and those tests passed.
- Confirmed PASS: actual approved grant through test socket and replay denial; revoked and expired leases denied; lease revocation blocked during execution; forged job denied; invalid peer denied; failed execution cannot replay; operator authorization and fixed-job restrictions.
- Skipped: signing key rotation test requires dedicated non-root trusted group.
- Scope limitation: these are repository tests, NOT proof of actual production systemd noop execution, real operator approval with production credentials, or production ledger reconciliation. Production acceptance remains pending. No service restart or production DB changes reported.


## Trusted-sidecar lease fencing implementation gate (2026-11-07)
- Operator explicitly authorized implementing trusted-sidecar-owned SQLite lease fencing and repeating integration/production acceptance.
- Source review confirms production broker currently calls execute_signed_grant(..., trusted_db_path=...) and attempts BEGIN IMMEDIATE on /var/lib/hermes-agency/agency.db, while ProtectSystem=strict only allows writes to /run/hermes-broker and /var/lib/hermes-broker. Production ledger approvals=0, audit=0, signed_grant_consumptions absent; production trusted DB approvals=0, active leases=0, execution_grants=0.
- Existing test_trusted_broker_socket.py uses socketpair, fake executor, mocked private-ledger check, and fixture SQLite; 77 passing tests DO NOT establish real production systemd noop.
- Target architecture: trusted UID owns the SQLite BEGIN IMMEDIATE transaction for the complete fixed-job execution; broker retains key verification, SO_PEERCRED, fixed-job allowlist, replay ledger, and systemd invocation. New private trusted lease-fencing IPC must authenticate root broker peer, cryptographically bind request to exact signed grant and single-use grant ID, support acquire/finish/abort with bounded lifetime, and fail closed on disconnect or sidecar crash. Avoid expanding broker ReadWritePaths to trusted DB and never expose worker socket or signing key.
- Required race tests: revoke-before-acquire denied; revoke-during-execution blocked; timeout/disconnect releases lock and fails closed; duplicate grant rejected; concurrent distinct grants serialize correctly; broker crash cannot silently authorize execution; ledger started/completed/failed reflects job outcome. Test with real isolated systemd noop and throwaway SQLite/key/socket before production deployment.
- Current implementation status: DESIGN/REVIEW ONLY; no production code, service configuration, or live acceptance changed. Do not mark production ready until implementation and all gates pass.


## Trusted lease fencing primitive implemented (2026-11-07)
- Added agency/trusted_lease_fence.py in commit 138f52c2182058b06fc6ce2c0cc34aad8e9d348a. The context manager opens the trusted DB rw, holds BEGIN IMMEDIATE, verifies live lease on that connection, and rolls back/releases lock on all exits.
- Added tests/test_trusted_lease_fence.py in commit 35de0b641bb2e5c85223e83b99f86ccd1ed13a78 with 5 cases: writer contention, revoked lease, expiry, exception cleanup, invalid path.
- These new tests have NOT been run on the VPS yet. The primitive is not wired into operator sidecar IPC or broker; existing production code and services remain unchanged. Do not mark end-to-end production acceptance complete.
- Next: run tests, design authenticated single-use broker-to-trusted permit protocol, integrate transaction lifetime and failure handling, then isolated real noop and ledger acceptance.


## Trusted lease primitive test evidence (2026-11-07)
- Operator fast-forwarded VPS checkout from 82acc07 to ac97436 using git pull --ff-only origin development/foundation.
- Executed python3 -m unittest -v tests.test_trusted_lease_fence tests.test_trusted_broker_socket tests.test_broker_grants.
- Result: Ran 18 tests in 0.462s, OK, TEST_EXIT_CODE=0; 5 new lease fencing tests, 6 trusted broker socket tests, 7 broker grant tests all passed.
- Production services were not restarted or deployed by this command. Trusted-sidecar IPC and real systemd noop remain unimplemented/unverified; production acceptance still pending.


## Experimental trusted lease IPC prototype (2026-11-07)
- Added agency/trusted_lease_ipc.py (57c6e7a, corrected acknowledgement ordering c722335) and tests/test_trusted_lease_ipc.py (a42cb6e). Protocol checks SO_PEERCRED root UID and signed grant, locks live trusted SQLite lease through job callback, acknowledges release only after transaction exits; disconnect triggers cleanup.
- New IPC tests cover lock held through callback, disconnect releases lock, and revoked lease rejected before callback. Tests NOT YET EXECUTED on VPS.
- IMPORTANT: This is an unconnected experimental primitive, NOT a deployable service or completed broker integration. It does not yet include socket filesystem ownership/lifecycle, broker-ledger replay wiring, bounded execution supervision or sidecar-crash job termination. The 10s socket timeout is not suitable for arbitrary job duration. No production runtime/service changes; production acceptance remains blocked.


## IPC prototype regression evidence (2026-11-07)
- Operator fast-forwarded VPS checkout ac97436 -> 18ffa31 and ran unittest modules test_trusted_lease_ipc, test_trusted_lease_fence, test_trusted_broker_socket, test_broker_grants.
- Result: Ran 21 tests in 0.676s, OK, TEST_EXIT_CODE=0, no skips; 3 new IPC tests, 5 fencing, 6 broker socket, 7 broker grants passed.
- This validates isolated callback lock lifetime and disconnect cleanup only. IPC remains unconnected to broker service, replay ledger, and real systemd execution; no production acceptance.


## IPC long-job timeout fix (2026-11-07)
- Commit 6b65237 changes experimental trusted_lease_ipc handshake timeout to no socket timeout once the lease is locked, preventing an arbitrary 10-second timeout from releasing the fence while an allowed job is still running.
- Not yet regression-tested on VPS; no production deployment or restart. This does not solve broker/sidecar crash safety, root broker ledger integration, or actual systemd noop acceptance. In particular, a crash after job start may release trusted lock while the systemd job continues; do not deploy before a bounded job-lifetime supervisor and fail-closed crash tests.


## Post-timeout-patch regression (2026-11-07)
- Operator pulled branch development/foundation to 2c06c40 on VPS and ran 4 unittest modules: trusted_lease_ipc, trusted_lease_fence, trusted_broker_socket, broker_grants.
- Result: Ran 21 tests in 0.598s, OK, TEST_EXIT_CODE=0 (3 IPC, 5 fence, 6 broker socket, 7 grants). No production service changes reported.
- Important limitation: these tests do NOT exercise a job lasting >10 seconds; timeout fix has no direct long-running regression test yet. IPC remains experimental and unconnected to production broker/ledger. Crash safety and real noop acceptance remain pending.


## Expanded IPC negative/long-job regression tests (2026-11-07)
- Added tests/test_trusted_lease_ipc_long_job.py (6c07a3e): fake job sleeps 10.25 seconds, asserts SQLite revocation is still blocked and lock releases after completion. No production job is run.
- Extended tests/test_trusted_lease_ipc.py (6d17698): reject incorrect SO_PEERCRED root UID and malformed completion; ensure lock released after malformed completion.
- These 3 new cases are NOT YET EXECUTED on VPS. Production broker/ledger integration and crash-safe systemd job supervision are still missing. Do not deploy or claim production acceptance.


## Expanded IPC test evidence (2026-11-07 02:13 UTC)
- Operator reported VPS checkout already up to date and executed 5 unittest modules: trusted_lease_ipc_long_job, trusted_lease_ipc, trusted_lease_fence, trusted_broker_socket, broker_grants.
- Result: 24 tests in 11.070s, OK, TEST_EXIT_CODE=0. New 10.25-second fake job kept trusted SQLite lock through the previous 10-second timeout boundary; wrong peer UID rejected; invalid completion released lock. No real systemd job was run.
- Production IPC wiring, replay ledger integration, sidecar/broker crash supervision, and actual approved noop acceptance remain pending; this is not production approval.


## Opt-in broker-to-trusted fence ledger integration (2026-11-07)
- Added execute_fenced_signed_grant in agency/systemd_broker.py (949c2bb): verify grant; connect to trusted lease IPC; require locked acknowledgement; atomically insert unique signed_grant_consumptions row in root ledger and commit before fixed-job executor; reject replay; update completed/failed only after fence completion acknowledgement. Root broker does not open trusted SQLite for writing in this new function.
- Added tests/test_fenced_broker_ledger.py (785c8e3): fake fixed-job ledger integration, lock during callback, one execution and replay denial. NOT YET RUN on VPS.
- IMPORTANT: Function is opt-in and NOT wired into supervised_broker production listener or operator sidecar socket lifecycle. A sidecar crash may release SQLite lease while an already-launched systemd transient unit continues; current function cannot guarantee kill-on-crash. No real noop acceptance, service restart or DB migration authorized. Next: implement supervised job lifetime / sidecar failure handling and acceptance tests before production wiring.


## Opt-in broker ledger IPC VPS verification (2026-11-07)
- Operator pulled development/foundation to 8dd8902 and ran test_fenced_broker_ledger, test_trusted_lease_ipc, test_trusted_lease_fence, test_trusted_broker_socket, test_broker_grants.
- Result: 34 tests in 1.157s, OK, TEST_EXIT_CODE=0. New atomic ledger consumption, replay denial, and trusted lock during fake job passed.
- Test-count caveat: BrokerFencedLedgerTests inherits TrustedLeaseIPCTests, so five inherited IPC test methods are discovered in both modules and counted twice. This is not 34 distinct scenarios.
- No production listener wiring, crash supervisor, or real systemd noop acceptance. Production remains gated.


## Duplicate-test cleanup and experimental fence-bound subprocess supervisor (2026-11-07)
- Commit 8617798: BrokerFencedLedgerTests now subclasses unittest.TestCase and reuses fixture setup/teardown without inheriting five IPC test methods. Expected distinct count for previous 34-test command becomes 29, subject to verification.
- Commit e49936d: added agency/fence_process_supervisor.py. Opt-in dedicated process-group subprocess runner watches trusted fence socket for EOF, rejects unexpected traffic, enforces deadline and kills/reaps its process group on failure. It is NOT wired to production systemd-run or broker.
- Commit 385534b: added 4 isolated tests for success, disconnect, timeout and unexpected IPC traffic. NOT YET RUN on VPS.
- SECURITY GATE: process-group termination does not terminate a detached systemd transient unit or independently reparented processes. Broker/sidecar crash safety requires systemd unit identity, stop/kill verification, and recovery semantics before real noop acceptance. No production restart or database changes.


## Supervisor and ledger regression verified on VPS (2026-11-07)
- Operator pulled development/foundation to 65b0b74 and ran six modules: test_fence_process_supervisor, test_fenced_broker_ledger, test_trusted_lease_ipc, test_trusted_lease_fence, test_trusted_broker_socket, test_broker_grants.
- Result: 33 tests in 1.341s, OK, TEST_EXIT_CODE=0. Four subprocess-supervisor cases passed (success, disconnect, timeout, unexpected traffic), as did atomic ledger/replay and existing regressions.
- Correction: test_trusted_lease_ipc methods still appear twice in the output. Reusing TrustedLeaseIPCTests.setUp/tearDown via import causes unittest loader to discover that imported TestCase class in test_fenced_broker_ledger too. Remove the module-level TestCase import or extract a non-TestCase fixture before claiming duplicate tests resolved.
- Production systemd transient unit kill-on-fence-loss, crash recovery, listener wiring and real noop acceptance remain unverified and blocked.


## Systemd unit lifecycle guard and test discovery cleanup (2026-11-07)
- Commit 48db661: avoid module-level import of discoverable TrustedLeaseIPCTests class into test_fenced_broker_ledger; the duplicate five IPC test methods should no longer be collected there. Await VPS verification.
- Commit fe7fa72: added opt-in agency/fenced_systemd_supervisor.py. Exact broker-owned hermes-fenced-<32hex>.service unit names only; stop and verify inactive/failed, no pending job and MainPID=0. Fail closed if stop/status cannot be verified. Not production-wired.
- Commit e7c702e: five mocked unit lifecycle tests (reject unrelated unit, successful stop verification, stop failure, status failure, active PID denial). Not yet run on VPS.
- SECURITY GATE: unit stop verification is not yet integrated into broker job launch, fence disconnect detection or sidecar crash recovery. A detached systemd unit may outlive the IPC connection until a persistent root watchdog kills it. Real noop acceptance remains blocked; no production changes or restarts.


## Systemd guard and deduplication verified on VPS (2026-11-07)
- Operator pulled development/foundation to 245873c and ran seven unittest modules: fenced_systemd_supervisor, fence_process_supervisor, fenced_broker_ledger, trusted_lease_ipc, trusted_lease_fence, trusted_broker_socket, broker_grants.
- Result: 33 tests in 1.132s, OK, TEST_EXIT_CODE=0; 5 mocked systemd guard tests, 4 subprocess supervisor tests, 1 ledger test, 5 IPC, 5 fence, 6 broker socket and 7 grant tests. IPC test discovery no longer duplicated.
- No real systemd unit was stopped or launched in this test. Systemd stop verification helper remains opt-in and unconnected to production broker. Crash recovery and real noop acceptance are still pending.


## Opt-in broker-to-systemd fence supervision integration (2026-11-07)
- Commits 419b699, f5a8b1e, f4a8991: execute_fenced_signed_grant accepts optional supervised_executor. The opt-in path derives a strict unique unit name from signed grant ID, passes the live fence socket to the runner, and calls stop_and_verify_unit on both success and failure. run_fenced_systemd_unit executes allowlisted fixed systemd-run with --unit, monitors fence EOF/unexpected data and 12s deadline, and fails closed. Default executor behavior unchanged; supervised_broker production listener is NOT wired.
- Commit c22417c: added four mocked broker unit lifecycle tests for successful verified cleanup, disconnect cleanup, cleanup verification failure, and invalid job. NOT YET VERIFIED ON VPS.
- Remaining production blocker: root broker abrupt crash cannot execute its own cleanup, so detached transient systemd units may survive. Need persistent independent systemd watchdog/recovery, race-free ownership and crash tests before real noop acceptance. No service restart or production DB modifications.


## Broker-to-systemd lifecycle suite verified on VPS (2026-11-07)
- Operator pulled development/foundation to 499a4af and ran eight unittest modules (fenced_broker_unit_lifecycle, fenced_systemd_supervisor, fence_process_supervisor, fenced_broker_ledger, trusted_lease_ipc, trusted_lease_fence, trusted_broker_socket, broker_grants).
- Result: 37 tests in 1.084s, OK, TEST_EXIT_CODE=0. Counts: 4 broker-unit lifecycle, 5 mocked systemd guard, 4 subprocess supervisor, 1 ledger, 5 IPC, 5 lease fence, 6 broker socket, 7 signed grants.
- These are unit/mocked and fake-executor tests, not a real systemd transient unit or forced root broker crash test. Broker abrupt-crash watchdog/recovery and production listener integration remain blocked. No production service changes or restarts.


## Independent fenced systemd orphan recovery primitive (2026-11-07)
- Commit af87e6f: added agency/fenced_unit_recovery.py. Root-only opt-in recovery enumerates loaded hermes-fenced-<32hex>.service units, rejects malformed names or failed enumeration, stops and verifies each via existing systemd guard, fails closed on any unsuccessful cleanup. Requires externally assured broker_stopped=True; never accesses trusted SQLite or issues grants.
- Commit 4da6919: added six mocked recovery tests. NOT YET RUN on VPS.
- Critical integration pending: no independent recovery service/unit is installed, no systemd broker stop/start ordering or restart gate is enforced, and no broker crash injection test has been performed. Passing broker_stopped=True alone is not a proof the broker is stopped; only trusted external orchestration may supply it. Do not enable production or run real noop yet.


## Independent fenced-unit recovery suite verified on VPS (2026-11-07)
- Operator pulled development/foundation to 679560e and ran nine unittest modules: fenced_unit_recovery, fenced_broker_unit_lifecycle, fenced_systemd_supervisor, fence_process_supervisor, fenced_broker_ledger, trusted_lease_ipc, trusted_lease_fence, trusted_broker_socket, broker_grants.
- Result: 43 tests in 1.134s, OK, TEST_EXIT_CODE=0. All six mocked recovery tests passed; no duplicate test discovery.
- No real broker crash, transient unit execution, independent systemd recovery service or startup/shutdown gate was exercised. Production remains unchanged and real noop acceptance blocked pending independent orchestration and isolated crash tests.


## Opt-in systemd lifecycle recovery hooks (2026-11-07)
- Commit 8e096f4: added CLI to agency.fenced_unit_recovery, returning nonzero on recovery failure. Explicit --broker-stopped is a caller assertion, NOT independently verified broker state.
- Commit c756f5c: added NON-INSTALLED deploy/examples/20-fenced-recovery.conf with ExecStartPre and ExecStopPost recovery hooks. Must not be deployed until deployment Python paths, startup ordering and crash safety are verified.
- Commit d58e6e1: three isolated recovery lifecycle CLI tests added; NOT YET RUN on VPS. No real crash injection performed.
- SECURITY BLOCKER: scanning systemctl list-units alone is not durable unit ownership; transient units can be unloaded. Hooks do not cover out-of-band broker processes or guarantee the trusted lease remains locked until independent cleanup after broker death. Add durable unit registry and systemd lifecycle coupling, then isolated crash tests, before enabling or real noop acceptance.


## Recovery lifecycle CLI verified on VPS (2026-11-07)
- Operator pulled development/foundation to 4f1d625 and ran ten unittest modules including fenced_recovery_lifecycle plus all nine prior suites.
- Result: 46 tests in 1.105s, OK, TEST_EXIT_CODE=0. All three new lifecycle CLI tests passed; the argparse usage message in the missing-gate negative test is expected.
- No independent recovery service/drop-in installed, no systemd daemon reload, no real transient unit or broker crash tested. Durable unit ownership, broker lifecycle coordination, and lease-loss race remain open blockers for production acceptance.


## Durable fenced-unit ownership prototype (2026-11-07)
- Commit c6e03fd: added agency/fenced_unit_journal.py. Root-owned SQLite journal registers allowlisted transient unit names as pending before launch, uses synchronous=FULL and fsync on parent directory; recovery verifies stop before changing pending to verified. Unverified units remain pending.
- Commit 8c4643e: optional journal_path in supervised_fenced_unit; records ownership before invoking runner. Production broker path does not yet supply journal_path.
- Commit 3055edc: four isolated journal tests added (prelaunch persistence, crash-before-launch record, recovery failure stays pending, invalid unit rejection). NOT YET VERIFIED ON VPS.
- Remaining: integrate journal recovery into independent CLI and startup gate, enforce single-broker systemd orchestration, test actual kill -9 while real transient unit runs, and resolve fence lock release race before production noop acceptance. Journal tests mock filesystem ownership checks and systemd controls; they do not prove actual crash safety.


## Durable ownership regression verified on VPS (2026-11-07)
- Operator pulled development/foundation to 8092869 and ran eleven unittest modules including fenced_unit_journal and all ten prior suites.
- Result: 50 tests in 1.116s, OK, TEST_EXIT_CODE=0. All four new journal tests passed: prelaunch persistence, pending recovery after simulated crash-before-launch, failure remains pending, invalid unit denied.
- Journal tests mock filesystem ownership verification and unit stop; no real broker SIGKILL, independent systemd recovery service, or transient unit was exercised. Production remains unchanged; recovery CLI integration, startup gate and crash safety remain pending.


## Durable journal recovery CLI and startup gate integration (2026-11-07)
- Commit b5ca1b8: opt-in recovery CLI --journal first checks journal exists, runs recover_owned_units (durable pending units), then systemd unit discovery/recovery; failures return nonzero and block subsequent startup in an installed ExecStartPre gate.
- Commit d0fda7a: non-installed systemd lifecycle drop-in example supplies /var/lib/hermes-broker/fenced-owned.sqlite to ExecStartPre and ExecStopPost. Deployment requires matching broker journal_path, real interpreter/module paths, root ownership and single-entrypoint enforcement.
- Commit db60c04: three mocked startup-gate tests added for journal-first, pending cleanup failure and missing journal. NOT YET RUN on VPS.
- CRITICAL: CLI flag --broker-stopped is still only a caller assertion. No production service/drop-in installed; no real SIGKILL while transient unit running; startup and trusted lease-loss race not proven. Never claim crash-safe or run production noop until isolated real lifecycle acceptance and systemd lifetime coupling pass.


## Durable recovery startup-gate regression verified on VPS (2026-11-07)
- Operator pulled development/foundation to 9deb8b8 and ran twelve unittest modules including durable_recovery_gate and all prior suites.
- Result: 53 tests in 1.142s, OK, TEST_EXIT_CODE=0. All three new mocked startup-gate tests passed. Expected argparse error output is from the missing --broker-stopped negative test.
- No systemd drop-in installed, no real transient unit or forced broker crash, and no proven race-free startup gate. Production unchanged. Next: isolated crash-injection harness and durable ownership/service lifetime coordination before any production acceptance.


## Isolated SIGKILL exercise prepared (2026-11-07)
- Commit 7306bb9: agency/isolated_fenced_crash_test.py runs a separate broker-like process, durably registers a test-only unit, SIGKILLs the process, verifies startup is denied while journal pending, then uses a FAKE in-memory systemd backend to simulate independent cleanup and verify startup is allowed only after journal marked verified.
- This test is not yet executed on VPS. It does NOT create or stop a real transient systemd unit, exercise a live trusted lease IPC disconnect, or prove automatic systemd startup ordering. Production untouched. Real systemd and fence-loss acceptance remain blockers.


## Isolated SIGKILL harness verified on VPS (2026-11-07)
- Operator pulled development/foundation to 6df586a and ran `python3 -m agency.isolated_fenced_crash_test`.
- Output: `isolated_sigkill_recovery=True`, `CRASH_TEST_EXIT_CODE=0`.
- This proves test-child SIGKILL plus persistent pending journal and simulated startup denial/recovery with a FAKE systemd backend. It does NOT prove real systemd transient-unit termination, actual systemd startup ordering, or live trusted lease disconnect safety. No production services changed.


## Real systemd acceptance harness prepared, NOT EXECUTED (2026-11-07)
- Commit 8e3d0bf: agency/real_systemd_crash_acceptance.py opt-in --execute harness. Creates random test-only hermes-fenced transient units executing /usr/bin/sleep 45 with RuntimeMaxSec=60, temporary root-owned journal under /run, SIGKILLs separate broker test process, verifies unit survives, injects cleanup failure preserving pending, then calls real stop_and_verify_unit via recover_owned_units. Separate socketpair EOF check stops/verifies a second test unit. Finally attempts cleanup.
- CAUTION: This is real systemd execution and must be approved/run on a disposable or maintenance test VPS, not blindly on production. It does not install or modify hermes-agency.service or broker production; systemd transient units are real and temporary.
- NOT PROVEN: actual systemd ExecStartPre startup gate ordering (failure injection is application-level), actual trusted lease IPC or SQLite fence loss, independent recovery unit automatic activation after broker crash, race-free lifetime coupling. Do not claim any of these pass. User must share test output before recording results.


## Real systemd acceptance first VPS run: partial pass, overall FAIL (2026-11-07)
- Operator ran `python3 -m agency.real_systemd_crash_acceptance --execute` on VPS. Output: `real_sigkill_recovery=PASS`, `startup_pending_failure_gate=PASS (application gate only)`, `socket_fence_eof_cleanup=PASS (not trusted lease IPC)`, then PermissionError `Fenced systemd unit stop failed` from repeated cleanup in `finally`; `REAL_SYSTEMD_TEST_EXIT_CODE=1`.
- Commit 60267c3 changes test harness finally blocks to stop only if unit still active; this is a test-harness fix, NOT a change to fail-closed production supervisor. Needs VPS retest. Still no real ExecStartPre ordering or trusted SQLite lease IPC verification.


## Real systemd crash acceptance VPS retest PASS (2026-11-07)
- Operator pulled development/foundation to 8d19bbd and reran `python3 -m agency.real_systemd_crash_acceptance --execute`.
- Output: `real_sigkill_recovery=PASS`, `startup_pending_failure_gate=PASS (application gate only)`, `socket_fence_eof_cleanup=PASS (not trusted lease IPC)`, `REAL_SYSTEMD_TEST_EXIT_CODE=0`.
- Demonstrates real transient-unit stop/recovery after SIGKILL of isolated test broker and real unit stop on synthetic socket EOF. Does NOT establish actual systemd ExecStartPre startup gating, real trusted lease/SQLite IPC disconnect safety, or automatic independent recovery after crash. Production untouched.


## Three-track real lifecycle acceptance requested (2026-11-07)
- Real systemd gate: commit 2c4a746 adds opt-in agency/real_systemd_startup_gate_test.py. Creates only a randomly named test unit in /run/systemd/system, verifies failing ExecStartPre blocks ExecStart marker and succeeding ExecStartPre permits it, then removes test unit. NOT RUN on VPS. This test uses systemctl daemon-reload and does not exercise the actual durable journal recovery CLI.
- Real trusted lease IPC end-to-end and automatic recovery on SIGKILL remain NOT IMPLEMENTED/NOT VERIFIED. Existing socketpair EOF acceptance is not a substitute. Do not claim the three-track acceptance is complete. Production service unchanged.


## Real ExecStartPre VPS test partial failure (2026-11-07)
- Operator ran `python3 -m agency.real_systemd_startup_gate_test --execute` after pulling 936848a.
- Output: `real_execstartpre_failure_blocks_execstart=PASS`, then `RuntimeError: Gate success failed to start test service`; `STARTUP_GATE_EXIT_CODE=1`. Thus startup denial verified, subsequent allow/start NOT verified.
- Commit f581113 adds diagnostic stderr and `systemctl status --no-pager --full` for the failing test unit; does not relax gate or change production. Needs VPS rerun with diagnostic output. Trusted IPC and automatic recovery still pending.


## Real startup gate failure diagnosed: 203/EXEC (2026-11-07)
- VPS diagnostic rerun exited 1. systemd status: `ExecStartPre=/run/hermes-gate-.../gate (code=exited, status=203/EXEC)`; test's earlier `real_execstartpre_failure_blocks_execstart=PASS` was a false-positive for intended gate logic (only verified ExecStart did not run). Exact 203/EXEC cause unconfirmed; /run execution restrictions possible.
- Commit b32a18c invokes gate as `/bin/sh <private-test-script>` and rejects 203/EXEC explicitly. Pending VPS retest; not yet PASS. Production untouched.


## Real systemd ExecStartPre acceptance VPS PASS (2026-11-07)
- Operator pulled development/foundation at fada2f4 and ran `python3 -m agency.real_systemd_startup_gate_test --execute`.
- Output: `real_execstartpre_failure_blocks_execstart=PASS`, `real_execstartpre_success_allows_execstart=PASS`, `STARTUP_GATE_EXIT_CODE=0`.
- Confirms isolated real systemd ExecStartPre script failure blocks ExecStart, and success permits ExecStart. Does NOT yet test journal-backed gate, actual trusted lease IPC or automatic recovery after crash. Production service unchanged.
