# Production Cutover Controller — Integration Status

## Implemented
- `agency.production_cutover_controller.cutover(adapter)` defines a single ordered handover and verified rollback transaction.
- `agency.production_cutover_simulation.SimulatedAdapter` provides isolated fault injection and replay rejection.
- `tests/test_production_cutover_controller.py` tests successful handover, failures at each phase, preserved consumed grants, and quarantine when rollback fails.
- Production operator admission lock provisioning and exclusive drain are implemented separately.

## Safety limits
**The controller is NOT production-executable.** There is no real adapter for systemd, broker socket routing, signed grant replay probes, durable quarantine, or sidecar deployment attestation. The CLI accepts `--simulate` only. No production services are changed by this module.

The simulated replay probe uses an in-memory set and is **not** evidence of real SQLite replay denial. Real replay denial must be acceptance-tested against the fenced broker and persisted ledger with the actual signed-grant protocol.

The `quarantine()` adapter contract must implement a durable, independently enforced admission denial that survives controller process exit and reboot. A mere Python boolean or held flock is insufficient.

## Before enabling real cutover
1. Build and validate a production adapter against isolated systemd services, with explicit route verification and version attestation for the running operator sidecar.
2. Make admission freeze and quarantine durable and independent of the controller process; prove restart/reboot behavior.
3. Prove exclusive ownership of the live ledger and journal, verify no in-flight jobs, and test old-to-new and new-to-old routing.
4. Run real signed-grant replay denial, crash recovery, and rollback tests in isolated staging with the same service configuration.
5. Verify ledger is never rolled back to an earlier snapshot; never run legacy and fenced brokers concurrently on the same state.
6. Obtain a production GO only after these checks and an explicit, reviewed deployment plan.

## Validation
Run `python3 -m unittest discover -s tests -q` and
`python3 -m agency.production_cutover_controller --simulate`.
These do not execute the production handover.

## Combined real-systemd acceptance (2026-11-07)
- Added `agency.isolated_cutover_crash_acceptance --execute`, which sequentially runs isolated systemd cutover fault injection and the existing real trusted-UID IPC / SIGKILL / independent recovery / journal-gated restart suite.
- These scenarios use isolated transient units and staging fixtures, not the actual fenced broker socket, grant verification and persisted signed-grant ledger across a broker restart.
- The combined runner intentionally prints `REAL_FENCED_BROKER_SOCKET_REPLAY_E2E=NOT_TESTED` and `PRODUCTION_CUTOVER_GO=NO` even if all included tests pass.
- Do not infer production readiness from a successful combined runner. A separate genuine candidate broker socket + signed grant + SQLite replay + SIGKILL E2E remains required.

## Active candidate broker crash and replay test
Run `python3 -m agency.real_candidate_socket_replay_e2e --execute` as root on the staging VPS. The opt-in harness uses an isolated signed `identity` grant, a real candidate Unix socket, a root-owned SQLite consumption ledger, a separate trusted SQLite fixture, and an ownership journal under `/run/hermes-staging/`. It waits for an active transient unit and a committed `started` grant before SIGKILL of the candidate broker, requires the pending startup gate to deny, explicitly recovers and verifies the unit stopped, restarts the candidate, and requires the same grant to be denied without an additional ledger row. This active-crash extension has not yet been run on the VPS. Recovery in this scenario is explicitly invoked by the test harness, **not** an independent PID1 OnFailure unit. Production cutover remains NO-GO pending integrated deployment attestation.

## Integrated PID1 candidate acceptance and production integration audit (2026-11-07)

Run `python3 -m agency.real_candidate_pid1_recovery_e2e --execute` as root on the staging VPS. This test creates two randomly named systemd staging services under `/run/systemd/system`, executes the actual isolated fenced broker socket with a real signed identity grant, SIGKILLs the broker's main process while the transient job is active, requires the independent `OnFailure` recovery service to stop/verify the owned unit, then restarts the actual broker and requires durable SQLite replay denial. The staging test is **committed but not yet VPS-verified**. No production services are stopped or rerouted. Test-only systemd unit files are removed on exit; private fixtures remain in `/run/hermes-staging` for investigation.

**Read-only source audit findings (not production runtime attestations):**
- **Sidecar:** `production_cutover_preflight.py` deliberately reports live sidecar admission-lock capability unattested. The sidecar's deployed executable, UID, shared admission lock participation, and actual broker socket routing must be attested on the live host.
- **Ownership:** `production_ownership_bootstrap.py` requires a root-owned freeze marker, exclusive admission drain, and both brokers independently verified stopped before creating a production ownership journal. Do not run it while the legacy broker is active. The journal path and independent recovery ordering must be provisioned and verified during an authorized maintenance window.
- **Admission:** `production_admission_drain.py` holds an exclusive flock and verifies lock inode stability. Live admission paths and handover behavior remain unverified; a passing isolated lock test does not attest the deployed sidecar.
- **Rollback:** `production_cutover_controller.py` provides a simulated/isolated adapter only; there is no authorized live adapter. Rollback must restore the legacy socket route, verify service health, retain consumed-grant ledger history, and quarantine if recovery is unverified. The `unfreeze()` call on the successful path is outside the exception handler; a production adapter must handle failure without reopening admissions unsafely.
- **Readiness:** Keep `PRODUCTION_CUTOVER_GO=NO` until the PID1 integrated test passes **and** the read-only preflight blockers are independently resolved with an explicit authorized cutover plan. Do not interpret this source audit as permission to mutate production.
