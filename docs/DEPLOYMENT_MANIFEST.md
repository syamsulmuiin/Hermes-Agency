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
