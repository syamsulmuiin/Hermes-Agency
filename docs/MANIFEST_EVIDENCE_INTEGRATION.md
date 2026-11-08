# Manifest-aware read-only evidence integration

`production_runtime_evidence.capture(manifest=...)` and
`production_recovery_wiring_evidence.inspect(manifest=...)` now accept an
optional validated deployment manifest. Their resolver and read-only systemd
state readers are injectable for isolated tests. The resolver obtains the
configured identities and executable on the current host.

Existing no-argument calls retain their pinned legacy behavior. No CLI
manifest flag is enabled, and existing production readiness gates remain
unchanged. This avoids silently replacing the current production trust anchor.

Runtime evidence still verifies the running sidecar's user, working directory,
PYTHONPATH, entrypoint, freeze, root-owned 0640 lock, and stable device/inode.
Recovery evidence still verifies loaded root-run units and required startup,
stop, and failure recovery wiring. Both remain non-authorizing.

Run:
`python3 -m unittest tests.test_manifest_evidence_integration tests.test_deployment_manifest -v`

The next step is to validate a trusted deployment manifest source, enforce
host filesystem ownership and provenance, and explicitly opt into the new
configuration at an authorized deployment boundary. Do not infer production
readiness from successful injection tests.
