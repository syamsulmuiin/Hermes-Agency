# Staging snapshot provenance and isolation — non-authorizing checkpoint

The portable staging foundation now includes:

- `agency.staging_snapshot_provenance.audit(snapshot, repo, commit)`: compares
  all regular files and Git blob hashes against a caller-pinned full SHA-1
  commit, checks root ownership, non-writable modes, hardlink count, symlinks,
  and file inventory. It rejects unsupported Git tree entries. **A caller
  must independently authenticate the expected commit**. Git object IDs
  are not signatures; repository trust and filesystem race hardening remain
  required before any execution.
- `agency.staging_isolation_evidence.inspect()`: observes Linux namespace
  links and visible PID1 without modifying state. Namespace observations
  cannot prove independent mount, socket, journal, network, or PID1 recovery
  isolation and never grant execute authorization.

No staging service installation, PID1 start/stop, fault injection, replay
ledger modification, or rollback was executed in this phase. The existing
`portable_staging_installer.execute()` remains unconditionally denied.

## Remaining acceptance work

1. Pin and authenticate a release commit and independently verify its
   provenance, immutable root-owned snapshot, and complete Git tree.
2. Verify separate staging VM/container mount namespace, PID namespace,
   systemd PID1, admission socket, state directories and journal using
   independent host-side evidence, not a self-declared flag.
3. Build a staging-only runner with explicit host resource allowlists and
   separate credentials; test startup gate, crash recovery, replay ledger
   persistence, and rollback through fault injection inside the isolated
   environment.
4. Preserve production freeze, production routes and all production services;
   never provision the production ownership journal.

```bash
python3 -m unittest tests.test_staging_provenance_isolation \
  tests.test_portable_staging_installer tests.test_portable_deployment_plan \
  tests.test_deployment_manifest tests.test_manifest_evidence_integration \
  tests.test_portable_host_capabilities -v
```

Passing unit tests is not evidence of a live isolated PID1 recovery test.
Production remains NO-GO.
