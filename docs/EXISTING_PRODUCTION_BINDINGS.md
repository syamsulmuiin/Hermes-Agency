# Existing production integration status

The portable backend now supports two explicit integration helpers:

- `bind_existing_admission()` uses the real exclusive `flock` on the same
  admission-lock inode used by the operator's shared lease.
- `bind_existing_evidence()` uses `ExistingProductionEvidence.freeze_verified`
  for read-only durable freeze verification. Runtime identity is checked
  through `production_runtime_evidence.capture`, installed recovery wiring
  through `production_recovery_wiring_evidence.inspect`, and an existing
  journal through `fenced_startup_gate.require_recovered`.

These helpers do not make a complete production backend. In particular,
runtime capture is observational, not behavioral admission proof. The
deployment manifest currently has no ownership-journal path; an explicit
path must be provided and the journal must already exist for the read-only
gate. No journal is created by these bindings.

**Not yet connected to live host operations:** freeze creation, quiescence,
broker stop/start, ownership journal bootstrap, route switch and rollback,
replay denial probe, service health, admission unfreeze and durable
quarantine. These remain explicit required callbacks. Do not bind staging
fakes or infer operations from unit names.

Existing `fenced_owned_recovery.recover_owned_journal` performs recovery
and can mutate state; never invoke it from an evidence/readiness check.
The existing `production_cutover_controller.cutover` remains the only
transaction state machine; `fenced_cutover_controller` remains read-only.

Validation:

```bash
python3 -m unittest tests.test_production_existing_evidence \
  tests.test_production_admission_bindings \
  tests.test_portable_production_backend \
  tests.test_production_maintenance_adapter -v
```

No production services, route, journal or admission freeze were changed by
this source-only integration. Production remains NO-GO.
