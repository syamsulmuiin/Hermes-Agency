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
