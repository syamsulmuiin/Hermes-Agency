# Real isolated staging acceptance — implementation checkpoint

Production remains NO-GO. No host services, admission freeze, routes, or
production journal are modified by this checkpoint.

## Completed code

- The pinned Git snapshot auditor rejects unexpected empty directories as
  well as unexpected files, symlinks, ownership/mode mismatches, and changed
  file hashes. Git tree validation does **not** authenticate the commit source.
- The staging isolation inspector remains observational and non-authorizing.
- The dependency-injected `staging_acceptance_simulation` orders snapshot,
  isolation, install, startup gate, broker crash, PID1 recovery, replay and
  rollback checks. Each injected failure stops subsequent phases.
  **Simulation never authorizes execution**, even when all callbacks return
  true.

## Still required before real acceptance

1. Establish an independently controlled staging VM or container with its own
   systemd PID1 and verified separation of mount, PID, network, IPC, sockets,
   state and credentials. No host production paths may be bind-mounted.
2. Authenticate a pinned release commit using a trusted operator-controlled
   channel, then harden snapshot inspection against filesystem TOCTOU with
   descriptor-relative traversal and immutable filesystem provenance.
3. Implement staging-only installation using a verified unit generator and
   isolated unit directory. Never write into the host systemd unit directory.
4. Execute actual broker failure injection, recovery, replay and rollback
   within the isolated PID1. Verify durable state across process restarts.
5. Audit the resulting evidence before considering any staging execute
   authorization. Production cutover requires separate approval and gates.

## Regression

```bash
python3 -m unittest tests.test_staging_acceptance_simulation \
  tests.test_staging_provenance_isolation \
  tests.test_portable_staging_installer \
  tests.test_portable_deployment_plan \
  tests.test_deployment_manifest \
  tests.test_manifest_evidence_integration \
  tests.test_portable_host_capabilities -v
```

The expected count is 38 tests. A passing test suite is **not** evidence of
real PID1 isolation, recovery or deployment.
