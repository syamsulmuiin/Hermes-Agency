# Real isolated staging runtime — implementation checkpoint

Production is NO-GO. No host systemd units are installed, no staging
container is launched, and no production service, freeze, route, or journal
is changed by this commit.

## Implemented

- `agency/staging_snapshot_fd.py`: root-owned snapshot inventory using
  directory file descriptors, `O_NOFOLLOW`, `dir_fd`, inode checks, and
  descriptor-based reads. The provenance auditor now consumes this inventory.
  This reduces pathname substitution risk but **does not eliminate all
  concurrent-mutation races**; an immutable source and authenticated pinned
  commit are still mandatory before execution.
- `agency/staging_runtime_topology.py`: validates the shape of an intended
  staging topology, with distinct state paths and identities. It cannot prove
  that a VM, PID namespace, systemd PID1, or state isolation exists.
- Regression tests cover normal snapshot inventory, symlinks, writable
  files, invalid topology, and non-authorizing results.

## Staging VM acceptance prerequisites

An operator must provide an independently isolated VM (preferred) or a
verified container with its own systemd PID1. Use **no host production
bind mounts**, no host systemd socket, no production credentials, and no
production journal. Staging service names, sockets, keys, admission locks,
freeze markers, ownership journal, and state must be unique to that guest.

The existing fenced broker, startup gate, recovery and replay components
must be configured only inside the guest. The acceptance suite must prove:
recovery precedes broker startup, startup gate denies pending ownership,
broker crash triggers independent PID1 recovery, replay ledger survives
restart and rollback, and failed rollback keeps staging quarantined.

The current `portable_staging_installer.execute()` is still unconditionally
denied. There is **no real PID1 E2E PASS** yet. Do not enable execute based
on these unit tests.

## Verification

```bash
python3 -m unittest tests.test_staging_snapshot_fd \
  tests.test_staging_runtime_topology \
  tests.test_staging_acceptance_simulation \
  tests.test_staging_provenance_isolation \
  tests.test_portable_staging_installer \
  tests.test_portable_deployment_plan \
  tests.test_deployment_manifest \
  tests.test_manifest_evidence_integration \
  tests.test_portable_host_capabilities -v
```
