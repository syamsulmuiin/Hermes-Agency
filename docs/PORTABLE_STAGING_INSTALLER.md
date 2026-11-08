# Portable staging installer — phase 1

**Status: non-executing foundation.** Production cutover remains NO-GO.

`agency.portable_staging_installer` exposes separate `plan`, `validate`,
and `execute` commands. Plan and validate are read-only and return status
code 2 even when observations succeed. Execute is **unconditionally denied**;
an isolation claim supplied by a caller is never accepted as proof.

```bash
python3 -B -m agency.portable_staging_installer plan \
  --manifest /etc/hermes-agency/deployment.json
python3 -B -m agency.portable_staging_installer validate \
  --manifest /etc/hermes-agency/deployment.json
```

The example manifest path must be installed separately in a trusted root-owned
directory; this change does not install it. Validation checks host identity
resolution, trusted manifest loading, root-owned snapshot inventory and file
permissions, and computes a snapshot inventory digest. The digest is **not**
an attestation of the intended Git commit: a separately pinned, authenticated
expected tree and full content comparison are still required.

`render_units()` returns inert candidate unit strings, derived from manifest
snapshot and candidate recovery unit names. These templates do not install
units and contain no live broker, recovery or journal execution. They are
not ready for service-manager installation or startup.

## Remaining prerequisites for execute

1. Isolated staging host/container/VM with independently validated mount,
   process, PID1, network, admission, and state separation from production.
2. A trusted snapshot provenance check against an explicitly pinned Git tree.
3. Verified systemd unit generation with safe escaping and no production
   paths or service names.
4. Separate staging ownership journal, admission lock, freeze and socket.
5. Failure-injected real startup gate, PID1 crash recovery, replay persistence,
   and rollback acceptance, with no access to production state.
6. An audited runner and operator-controlled staging-only authorization.

None of these requirements is waived by unit tests or a self-declared
`isolated=true` flag. Existing production services, freeze, route, and
journal remain untouched.

Tests:

```bash
python3 -m unittest tests.test_portable_staging_installer \
  tests.test_portable_deployment_plan tests.test_deployment_manifest \
  tests.test_manifest_evidence_integration \
  tests.test_portable_host_capabilities -v
```
