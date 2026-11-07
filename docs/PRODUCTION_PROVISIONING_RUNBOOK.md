# Hermes optional broker + operator sidecar — deployment preparation

**Status: reviewed design only. Not permission to install, provision, start, enable, or restart services.**

## Verified prerequisites and staging

- Development branch: `development/foundation`; hardened isolated systemd acceptance PASS; production-based staging imports 14/14 PASS.
- Installed production Python package: 27 identical modules, 1 different (`trusted_execution.py`), 22 missing. An explicit runtime overlay is required; never copy only `trusted_execution.py`.
- Worker UID 995, trusted UID 997/private primary GID 986, shared worker transport GID 987 (verify again immediately before deployment). **Never** make broker signing key group 987.
- Existing `hermes-agency.service` is active. No change to its unit, socket, state, or startup command is proposed.
- Template files: `deploy/hermes-signed-broker.service.example`, `deploy/hermes-operator-sidecar.service.example`, and `deploy/hermes-optional-runtime.tmpfiles.example`. They are **not installed** by this repository.

## Preparation gate — read-only

1. Confirm running production Python modules and installed version; compare hashes and complete module dependencies. Review and package exactly the 11 runtime files listed in `deploy/test_runtime_staging_imports.sh`, preserving all other installed files. Stage first; record original `trusted_execution.py` checksum and a root-only rollback copy before any authorized replacement.
2. Review broker and operator unit files, verify both with `systemd-analyze verify` using temporary `.service` filenames, and run `python3 -m agency.broker_unit_audit` on the broker template. Review `systemd-analyze security` as advisory; do not weaken fail-closed checks to silence warnings.
3. Verify `hermes-trusted` primary group is private and `hermes-worker` is not in that group. Verify `/var/lib/hermes-agency`, `keys`, SQLite, signing key, and auxiliary SQLite files retain trusted ownership and private permissions. Never print or copy secrets.
4. Confirm filesystem layout, free disk space, restart behavior, transient test results and service dependencies. Schedule a maintenance window and make an encrypted root-controlled backup of trusted state (including SQLite consistency) only after explicit approval. Backups must not be checked into Git.

## Approved-only provisioning order (DO NOT RUN YET)

1. After explicit approval, deploy audited runtime overlay into root-owned `/opt/hermes-agency/agency` with an atomic release strategy or pre-staged rollback copy. Do not overwrite the original `trusted_execution.py` without a verified rollback.
2. Create root-owned `/etc/hermes-broker` with non-world-writable permissions and private-group traversal; root-only `/var/lib/hermes-broker` directory mode 0700. Use `agency.signed_broker_service.provision_broker_key` as root to create `/etc/hermes-broker/signing.key` exactly once (64 raw random bytes, root:private-trusted-GID, 0640). Never reuse the existing worker credential signing key; never echo broker key.
3. Initialize `/var/lib/hermes-broker/ledger.sqlite` once via `agency.systemd_broker.initialize_ledger` as root. Ledger file is root-owned 0600. Preserve it across rollback and restart; do not recreate on every boot.
4. Install `deploy/hermes-optional-runtime.tmpfiles.example` as a separately approved tmpfiles configuration, then apply only that configuration. It creates `/run/hermes-broker` mode 0710 root:private-trusted-group and `/run/hermes-operator` mode 0700 trusted:private-trusted-group. Runtime directories are recreated on boot, but sockets are created by the respective processes, not by tmpfiles. Confirm the existing worker socket directory is unchanged.
5. Generate a **new** cryptographically random 32-byte operator secret offline and store it only in an operator-controlled secure password manager. Run `python3 -m agency.operator_provision --path /var/lib/hermes-agency/keys/operator-verifier.json --identity operator` interactively **as the trusted UID with its private GID**. The verifier is a separate trusted-owned 0600 file; never store plaintext secret in the repo, CLI args, shell history, env, logs or chat.
6. Install reviewed broker and sidecar unit templates as `hermes-signed-broker.service` and `hermes-operator-sidecar.service`, respectively, with `systemd-analyze verify` and explicit permission/owner checks. Do not start either unit until all prerequisite checks pass. Start broker before sidecar; validate socket ownership and deny paths before testing a fixed allowlisted `noop` with a **real approved** request and active worker lease. Do not fabricate approvals in production.
7. Enable optional units on boot **only** after separate authorization and successful live validation. Startup order in the operator template is `After=`, not `Requires=`; missing broker connection fails closed at execution time.

## Rollback — approved deployment only

- Stop and disable **only** `hermes-operator-sidecar.service` and `hermes-signed-broker.service`; verify their sockets are gone. Leave `hermes-agency.service` running.
- Keep `/var/lib/hermes-agency/agency.db`, credential signing key, operator verifier, broker key and root ledger for audit and potential recovery. Do **not** delete or regenerate keys/ledger as part of rollback.
- If the optional runtime overlay must be reverted, restore only the explicitly replaced files from a recorded root-controlled rollback copy during an approved maintenance procedure. Do not assume replacing files changes already-running Python processes; avoid unapproved restarts.
- Verify `systemctl is-active hermes-agency.service` and worker-stage health. Record exact timestamps, unit logs, file hashes, backup location and final status.

## Open blockers before activation

- Final units and tmpfiles have not been installed or validated against actual production paths and permissions.
- Static unit verification and staged import checks are not equivalent to live production provisioning.
- Production SQLite concurrent access, operator verifier storage, deployment overlay rollback and boot-time ordering must be reviewed.
- **Explicit approval required** before any production filesystem change, credential provisioning, systemd unit installation or service activation.
