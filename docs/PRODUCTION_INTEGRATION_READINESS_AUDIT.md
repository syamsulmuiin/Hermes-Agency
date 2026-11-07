# Production Integration Readiness Audit — 2026-11-07

**Scope:** read-only architecture review of the `development/foundation` code and candidate systemd manifests. **No production deployment, enablement, or cutover is authorized.**

## Verified baseline
The operator's VPS run reported 301 unit tests OK (one skipped) and the isolated persistent candidate E2E PASS: socket, signed grant, replay denial, SQLite lease lock, SIGKILL pending gate, PID1 recovery, restart. Both existing production services remained active. These results validate the **isolated test fixture**, not the production manifests.

## Launch and protection paths
1. **Current signed broker path:** `agency/signed_broker_service.py` -> `agency/systemd_broker.py:handle_signed_connection` -> `execute_signed_grant`. This path is distinct from the persistent fenced candidate and does **not** pass through `fenced_staging_broker.staging_broker_job` or the ownership journal/startup gate. Confirm the active service's actual ExecStart and callers on the VPS before asserting coverage.
2. **Fenced candidate:** `fenced_broker_candidate.serve_candidate` -> `fenced_staging_launcher.run_staging_session` -> `fenced_staging_broker.staging_broker_job` -> `fenced_staging_serialization.staging_launch` (flock, gate, atomic replay admission, durable journal registration) -> trusted SQLite lease peer + systemd transient-unit supervisor -> stop/verify + journal completion.
3. **Crash recovery:** candidate systemd `ExecStopPost` and `OnFailure` invoke `fenced_owned_recovery`, which takes the same journal flock and stops/verifies pending units. Startup `ExecStartPre` requires a recovered journal.

## Findings and risk assessment
- **P0 / coverage gap:** The currently active signed broker is not demonstrated to use the new fenced candidate lifecycle. Isolated E2E success must not be described as production launch-path protection. Inventory all actual production ExecStart commands and fixed-job call sites.
- **P0 / unverified production manifest:** `deploy/systemd/hermes-fenced-broker-candidate.service` references `/run/hermes-broker/fenced-candidate.sock`, `/var/lib/hermes-broker/owned-units.sqlite`, and `/var/lib/hermes-agency/agency.db`; unlike the ephemeral fixture, it has `ProtectSystem=strict`, `ProtectHome=yes`, and `ReadWritePaths=/run/hermes-broker /var/lib/hermes-broker`. Verify socket directory provisioning, trusted DB write access for the nonroot lease peer, systemd sandbox behavior, and root-owned key permissions in a separate staging deployment. Do not enable the production candidate to test this.
- **P1 / startup gate concurrency:** `ExecStartPre` checks the journal without acquiring `staging_journal_lock`. `serve_candidate` also calls `require_recovered` outside that lock at startup and on each request. The actual launch path *does* gate under the lock; document/test all start/recovery interleavings, especially a separate service using the same journal.
- **P1 / admission crash window:** `staging_launch` consumes a grant in the ledger before registering its unit in the journal. Crash in between burns the grant without starting work (fail-closed, availability loss). Test this explicitly; do not attempt automatic replay.
- **P1 / journal durability and host crash:** `register_before_launch` commits with SQLite FULL synchronous, but the tests supplied demonstrate SIGKILL, not power loss, reboot, disk-full, SQLite corruption, or failed fsync. Recovery must fail closed for these cases.
- **P1 / broker response handling:** `serve_candidate` catches `PermissionError`, `ValueError`, and `OSError`; unexpected `sqlite3.Error` and other exceptions terminate the service, triggering systemd recovery. Verify that denial is never mistaken for successful execution and that service failure is observable.
- **P1 / lifecycle failure windows:** Test crash after journal registration but before systemd-run, while systemd-run is creating the unit, after unit exits but before journal verification, and during stop verification. Confirm PID1 recovery and startup denial under each.
- **P1 / watchdog ordering:** The candidate manifest declares `After` + `Requires` for a oneshot recovery unit and `OnFailure`/ `ExecStopPost` for post-crash recovery. Verify systemd dependency ordering, overlapping triggers, service restart attempts, and recovery failure behavior with `systemd-analyze verify` and a disposable staging unit. Never infer ordering solely from the passing isolated fixture.
- **P2 / test-fixture differences:** `isolated_candidate_runner._runner` substitutes a sleep/hold transient unit for `identity`; this is deliberately not the production runner. Repeat key crash windows against the real runner in an isolated systemd profile.
- **P2 / fixture side effect:** `isolated_candidate_acceptance.run` changes the shared `/run/hermes-staging` directory mode to 0711; consider avoiding changes to a pre-existing shared staging directory in a later scoped hardening patch.

## Required staging acceptance before proposing cutover
1. Read-only production inventory: `systemctl cat`, `systemctl show`, socket paths, trusted UID/GID, effective file ownership/modes; redact secrets.
2. Static candidate unit verification and sandbox review on staging; ensure distinct socket and independent journal/ledger; no production path reuse during testing.
3. Fault injection matrix for all P1 crash windows, concurrent grant/replay attempts, recovery failure, startup gate denial, journal corruption and host reboot; record expected vs observed results.
4. Confirm every permitted production execution entrypoint is either fenced or explicitly excluded by scope; provide a migration/cutover design with rollback and operator approval gate.
5. Update this report and `PROJECT_STATE.md` with evidence; do **not** enable candidate production services without explicit approval.

**Status:** AUDIT FINDINGS RECORDED; PRODUCTION INTEGRATION READINESS = NOT YET VERIFIED.
