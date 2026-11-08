# Production cutover integration reconciliation

Status: **NO-GO**. This document records the gap between previously
successful tests and the currently observed deployed runtime. It does not
authorize cutover, restart services, create the production ownership journal,
change routes, or remove the admission freeze.

## Evidence already available

- Full regression suite: 456 tests, OK, one skipped (operator-reported).
- Production maintenance adapter: 7 tests, OK, including injected failures,
  replay-ledger identity, rollback, and quarantine (operator-reported).
- Snapshot acceptance preflight: PASS; 263 files (operator-reported).
- Deployed runtime identity and installed recovery wiring: PASS in the
  read-only stage-1 report (operator-reported).
- Earlier staging acceptance runs: exclusive drain, socket handover, replay
  persistence, rollback and combined E2E PASS. These are not interchangeable
  with a live production cutover attestation.

## Integration gap — inspect before changing anything

1. `agency/production_maintenance_adapter.py` defines an injected backend
   contract. Its tests use `FakeBackend`. A verified production implementation
   of every required operation is not established by these tests.
2. `agency/production_readiness_stages.py` and
   `agency/fenced_cutover_controller.py` contain host-specific defaults,
   including candidate paths and service names. Existing manifest resolution
   should be reused instead of adding another hardcoded VPS profile.
3. The observed ownership journal
   `/var/lib/hermes-broker/owned-units.sqlite` is absent. This is a deliberate
   safety invariant during preparation, not an instruction to provision it.
4. The current stage-1 report does not behaviorally attest live sidecar
   admission locking, exclusive production drain, route handover/rollback,
   independent PID1 recovery, or empty-/run boot provisioning.
5. `fenced_cutover_controller.py` is a read-only gate. Do not add an execute
   path or convert prior PASS output into authorization.

## Minimal finishing sequence

- Identify and reuse existing signed broker, sidecar, journal, recovery,
  admission and routing functions; map each backend method to a real
  implementation or explicitly mark it unsupported.
- Derive host-specific paths, identities and units from the validated
  deployment manifest. Refuse incomplete or inconsistent manifests.
- Keep all maintenance operations behind an explicit operator-approved
  window, pinned runtime identity and stable exclusive admission lock.
- Preserve the persistent replay ledger across success and rollback.
  On rollback failure, keep durable quarantine and admission closed.
- Only after operator-reviewed integration and current-host attestation
  should a separate controlled maintenance procedure be considered.

## Current deployment invariants

The operator's latest read-only report showed all three production services
active, admission freeze preserved, and the production ownership journal
absent. No cutover operation was requested or executed in this reconciliation.
