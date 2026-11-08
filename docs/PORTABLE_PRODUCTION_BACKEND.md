# Portable production maintenance backend

`agency/portable_production_backend.py` bridges the existing
`ProductionMaintenanceAdapter` and `production_cutover_controller.cutover`
to an explicitly supplied, reviewed set of host operations. Paths, units
and identities come from the validated deployment manifest and resolver.

**This is an integration contract, not a deployable live host backend.**
It does not include a production CLI, shell commands, default systemd
actions, journal creation, route switching, or admission reopening.
There is no fallback to staging or fake operations. Every host operation
must be supplied and reviewed separately before live use.

Host operation callbacks receive the validated resolution as their first
argument. The exclusive drain callback must return a context manager that
holds the real admission lock throughout the transaction. All other
callbacks are denied outside that drain. The existing maintenance adapter
checks runtime identity, lock inode, freeze, replay ledger identity,
handover and rollback; the existing controller handles rollback and
quarantine when an operation fails.

**Remaining live integration:** bind each callback to audited existing
sidecar, broker, journal, recovery and routing operations. Verify durable
freeze/quarantine, stable lock inode, journal bootstrapping, replay
persistence and independent PID1 recovery in the target environment.
The validated manifest alone is never authorization. Do not call
`cutover()` with production operations before these proofs and an
explicit maintenance window.

Test the bridge without touching production:

```bash
python3 -m unittest tests.test_portable_production_backend \
  tests.test_production_maintenance_adapter -v
```

Production remains NO-GO. Keep all three services active, the admission
freeze present, and the production ownership journal absent.
