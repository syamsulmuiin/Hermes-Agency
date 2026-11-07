# Production maintenance adapter

**Status: NOT AUTHORIZED — production NO-GO.**

`agency.production_maintenance_adapter` is an inert, dependency-injected adapter for the existing `production_cutover_controller.cutover()` state machine. It is distinct from the staging adapter. It has no executable production entrypoint and does not operate on systemd, production sockets, routes, databases, or freeze files by itself. `fenced_cutover_controller.py` remains read-only.

The operator must independently approve a maintenance window, pinned 40-character commit, expected runtime identity, and admission-lock device/inode. A reviewed host backend must implement all methods documented in the adapter class, with fail-closed semantics, persistent exclusive lock ownership, durable freeze/quarantine, quiescence, journal recovery, verified service and route transitions, and a real replay rejection probe. The backend must verify each effect, not just command exit codes.

The replay ledger is **never** reset or restored by rollback. Its identity is checked before and after journal bootstrap, before service handover, during replay verification, and after rollback. On rollback failure, quarantine must remain durable after process exit and admission must stay closed. Quarantine failures are critical and require manual recovery; they must never be interpreted as successful rollback.

Run the dependency-injected unit suite with `python3 -m unittest discover -s tests -p 'test_production_maintenance_adapter.py' -v`. These tests do not validate live host behavior. Before any production use, separately review and implement the backend, validate lock/freeze inode and service identity under real systemd, exercise crash recovery and rollback in an isolated environment, and obtain explicit maintenance authorization. No staging PASS grants that authorization.

## Isolated host backend and evidence evaluation

`agency.production_host_backend.IsolatedHostBackend` uses an existing regular admission-lock file (mode 0640), nonblocking exclusive `flock`, descriptor/path inode comparison, and a required injected `admission_participation_verified()` attestation. It never creates a lock, freeze, journal, or service. Its default operations provider denies all host actions. A test root must be used for acceptance; this is not a reviewed production driver.

`agency.production_maintenance_readiness.evaluate()` checks 12 evidence fields and an explicit independent live attestation flag. Even a complete mapping returns `EVIDENCE_COMPLETE_NOT_AUTHORIZED`, **not** permission to execute production cutover. The CLI always returns NO_GO. An independent operator-controlled production authorization mechanism remains necessary.

Run `python3 -m unittest discover -s tests -p 'test_production_host_backend.py' -v` on a development/staging host. These newly committed tests have not been executed on the production VPS by this change. The host backend still needs independently reviewed real service, journal, route, and replay operations, plus crash-recovery acceptance. Production remains NO-GO; do not remove the existing freeze.
