# Production maintenance adapter

**Status: NOT AUTHORIZED — production NO-GO.**

`agency.production_maintenance_adapter` is an inert, dependency-injected adapter for the existing `production_cutover_controller.cutover()` state machine. It is distinct from the staging adapter. It has no executable production entrypoint and does not operate on systemd, production sockets, routes, databases, or freeze files by itself. `fenced_cutover_controller.py` remains read-only.

The operator must independently approve a maintenance window, pinned 40-character commit, expected runtime identity, and admission-lock device/inode. A reviewed host backend must implement all methods documented in the adapter class, with fail-closed semantics, persistent exclusive lock ownership, durable freeze/quarantine, quiescence, journal recovery, verified service and route transitions, and a real replay rejection probe. The backend must verify each effect, not just command exit codes.

The replay ledger is **never** reset or restored by rollback. Its identity is checked before and after journal bootstrap, before service handover, during replay verification, and after rollback. On rollback failure, quarantine must remain durable after process exit and admission must stay closed. Quarantine failures are critical and require manual recovery; they must never be interpreted as successful rollback.

Run the dependency-injected unit suite with `python3 -m unittest discover -s tests -p 'test_production_maintenance_adapter.py' -v`. These tests do not validate live host behavior. Before any production use, separately review and implement the backend, validate lock/freeze inode and service identity under real systemd, exercise crash recovery and rollback in an isolated environment, and obtain explicit maintenance authorization. No staging PASS grants that authorization.
