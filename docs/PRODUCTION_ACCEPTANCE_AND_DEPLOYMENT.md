# Production-like Acceptance and Controlled Deployment Plan

Status: **PREPARATION ONLY**. No production authorization, installation, restart, or secret provisioning.

## Gate A: isolated production-like runtime acceptance

On the VPS development checkout, as root:

```bash
cd /root/Hermes-Agency
git pull --ff-only origin development/foundation
bash -n deploy/test_production_equivalent_acceptance.sh
echo "SYNTAX_EXIT_CODE=$?"
bash deploy/test_production_equivalent_acceptance.sh
echo "HARDENED_RUNTIME_EXIT_CODE=$?"
systemctl is-active hermes-agency.service
```

The new harness uses throwaway fixtures under `/run/hermes-supervised-e2e.*`, transient systemd units and independent database, keys, broker ledger, operator verifier and operator secret. It enables `ProtectHome=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, the broker's capability bounding set and most other production broker restrictions. It retains the existing negative tests for worker socket denial, incorrect operator secret and stale HMAC grants. It must finish with `HARDENED_RUNTIME_EXIT_CODE=0` and the existing production service active.

**Limitations:** this is *production-like*, not byte-for-byte production equivalence. Transient units still use `ReadWritePaths` for temporary fixtures, `/run` instead of final locations, and test-only secrets. No production ledger or SQLite is touched. This script has not yet been executed on the VPS; report its actual output before claiming PASS. Inspect transient-unit journal on any failure and fix the smallest root cause. Never bypass a failing hardening control just to obtain PASS.

## Gate B: deployment prerequisites (read-only)

- Confirm the production checkout revision and audited code hashes. The currently installed `/opt/hermes-agency` version is not yet confirmed to match development.
- Confirm worker UID 995, trusted UID 997/private GID 986, shared transport GID 987. **Never grant broker key access to GID 987**.
- Verify the real trusted SQLite and credential secret paths and their owner/mode, without reading or copying their contents.
- Verify the operator verifier is distinct from the worker credential. Provision its verifier only after explicit approval; operator secret must not be in shell argv, environment, logs, repository, or chat.
- Review broker execution allowlist, systemd job template and actual `ReadWritePaths`, `CapabilityBoundingSet`, sandbox settings, service dependencies, runtime directory lifecycle and logs.
- Define a maintenance window and backup/restore policy for the trusted SQLite and credential state. Never overwrite or migrate live state implicitly.

## Gate C: provisioning design (requires separate explicit approval)

1. Install audited code in the root-owned production application tree, with a recorded commit and rollback copy. Do not replace the running service or change worker-facing protocol.
2. Create `/etc/hermes-broker` root-owned and non-writable by untrusted users. Create broker key with `agency.signed_broker_service.provision_broker_key`: exactly 64 random bytes, owner root, group trusted **private** GID, mode 0640. This is a separate key from `/var/lib/hermes-agency/keys/signing.key`.
3. Create root-owned `/var/lib/hermes-broker` for the private root-only replay ledger and root-owned `/run/hermes-broker` mode 0710, group trusted private GID. Define a persistent mechanism to recreate the runtime directory after reboot before broker starts.
4. Create `/run/hermes-operator` owned by trusted UID and its **private** GID, mode 0700. Its socket must be 0600 and the listener must enforce root peer UID. Recreate this directory before operator starts; do not reuse `/run/hermes-agency`.
5. As the trusted UID, provision a separate scrypt verifier using `agency.operator_provision` with an offline-generated 32-byte operator secret entered interactively; protect the verifier with 0600 and store the secret only in an operator-controlled secure manager.
6. Install separate audited root broker and trusted-private-group operator units, with `RequiresMountsFor`, explicit ordering and restrictive sandbox. Verify with `systemd-analyze verify` on real `.service` files. Check startup and shutdown using test-only no-op grants before authorizing any real action.
7. Keep `hermes-agency.service` untouched unless a separately approved change is unavoidable. No live approval or arbitrary command execution is part of acceptance.

## Gate D: activation and rollback (not authorized)

Activation requires explicit user approval after Gate A passes and the exact production unit files, credential paths, backups, tests, rollback commands and expected downtime have been reviewed.

Rollback must stop/disable **only** the optional operator sidecar and root broker, then verify the existing worker service remains healthy. Do not delete the trusted SQLite, operator approval records, broker ledger, or production credentials as part of rollback. Restore previous application code only under an independently approved change procedure. Keep the signed-grant ledger for audit.

## Recorded VPS baseline (2026-11-07)

- Unit tests: 218 OK, 1 skipped; original isolated acceptance PASS.
- `systemd-analyze verify` on temporary broker `.service` copy: exit 0.
- Systemd 255; production worker service uses `agency.single_vps_service` from `/opt/hermes-agency`.
- `/var/lib/hermes-agency` and `keys`: 0700 trusted:trusted; `agency.db` and `keys/signing.key`: 0600 trusted:trusted.
- Broker production directories do not yet exist, by design.
