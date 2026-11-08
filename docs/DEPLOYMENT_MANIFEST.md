# Deployment manifest and runtime resolution

The versioned `deploy/deployment.manifest.example.json` is a per-host
configuration example, **not** an active production configuration.
`agency.deployment_manifest.validate` rejects unknown keys, invalid
absolute paths, duplicate paths, and invalid service/user names.
`load` accepts only a bounded regular file without hard links or symlinks.
`resolve` resolves configured service identities to host UID/GID values and
finds the host's systemctl binary. It does not create users, change permissions,
start services, acquire locks, or validate sandbox execution.

Integration into existing production evidence gates is intentionally deferred
until cross-host fixture tests establish compatibility. Existing production
paths and pinned snapshot verification remain unchanged and fail-closed.
Runtime discovery is not proof of lock behavior, recovery, or safe cutover.

## Trusted manifest loading (read-only)

`load(path)` requires an absolute canonical path, root-owned non-writable
ancestor directories without symlinks, and a root-owned regular manifest
with a single hard link, no group/other write permissions, and a 16 KiB
size limit. It opens with `O_NOFOLLOW`, reads through a pinned descriptor,
and rejects inode replacement observed during the read. This is a
fail-closed configuration check, not a cutover authorization.

`resolve(manifest)` verifies that the resolved `systemctl` executable
and its directory chain are root-controlled and not group/other writable
before querying systemd. Resolution never starts or modifies services.

These checks do not establish an immutable deployment or eliminate every
possible privileged concurrent filesystem race. Only root-controlled
deployment locations should be used; do not load a manifest from `/tmp`
or another writable ancestor. No production gate opts into this manifest
automatically.

Run `python3 -m unittest tests.test_deployment_manifest
tests.test_manifest_evidence_integration tests.test_portable_host_capabilities -v`.
