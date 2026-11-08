# Portable cross-VPS deployment boundary

Status: **planning and simulation only; production NO-GO**.

The portable deployment planner accepts a root-controlled deployment manifest
using `agency.deployment_manifest.load`, resolves the current host's user/group
IDs and trusted systemctl executable, and emits a non-executable report.
It does not create identities, directories, unit files, ownership journals,
admission locks, or sockets. It never starts/stops/reloads a service, changes
routing, or removes admission freeze.

Run only with a manifest installed under a root-controlled directory:

```bash
python3 -B -m agency.portable_deployment_plan \
  --manifest /etc/hermes-agency/deployment.json --read-only
```

The path above is an example; no manifest is installed by this change.
A valid plan intentionally returns exit code **2**, as it cannot authorize
deployment or cutover. Do not treat a plan report as runtime attestation.

## Compatibility matrix (simulated)

| Profile | Trusted UID | Trusted GID | systemctl | Status |
| --- | ---: | ---: | --- | --- |
| Ubuntu | 997 | 987 | /usr/bin/systemctl | Simulated |
| Debian | 1101 | 1102 | /bin/systemctl | Simulated |
| Armbian | 2001 | 2002 | /usr/local/sbin/systemctl | Simulated |

The tests inject host identities and executable paths; they **do not**
claim that these binaries or users exist on any actual host. Production
execution still requires real host discovery and independent attestation.

## Trust boundaries

- Manifest validation rejects extra keys, path traversal, and invalid units.
- Trusted file loading checks root ownership, writable ancestors, symlinks,
  file link count, and file identity during the read.
- Resolver output must preserve the manifest's path and unit mapping and
  must not assert runtime behavior, sandbox authorization, or cutover.
- The planner always denies broker execution, admission, installation,
  and cutover regardless of simulated compatibility.
- Existing broker, admission, recovery, and production readiness gates
  remain unchanged and must independently enforce their security policies.
- A manifest is **configuration**, never a signed grant, admission lock,
  ownership journal, or proof of recovery.

Run the targeted tests:

```bash
python3 -m unittest tests.test_portable_deployment_plan \
  tests.test_deployment_manifest tests.test_manifest_evidence_integration \
  tests.test_portable_host_capabilities -v
```

Next deployment work requires a separately reviewed staging installer that
verifies immutable artifacts, user/group permissions, and systemd unit
provenance. Do not opt production gates into a new manifest automatically.
