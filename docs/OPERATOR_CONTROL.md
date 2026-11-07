# Local Authenticated Operator Sidecar (Opt-in)

## Architecture and deployment status

The operator channel is a **separate non-root trusted-UID sidecar**, not an
additional listener in the worker-facing `hermes-agency.service`. It shares
the existing trusted SQLite database and credential signing secret with the
live service, but uses its **own private primary group** so it can read the
root-owned broker signing key without giving that group to worker processes.

Existing worker-stage socket, worker group, worker service CLI, and production
service unit remain completely unchanged. Nothing is installed or enabled by
committing this code. The operator sidecar is currently development-only and
requires isolated acceptance before any production activation.

Operator authorization flow:

1. A valid task, active worker lease and pending action approval exist in the
   trusted SQLite state.
2. A local **root** operator connects to a separate Unix socket inside a
   trusted-UID-owned directory (0700). The socket is owner-only (0600).
3. `SO_PEERCRED` must report UID 0 **before** the listener reads request data.
   Filesystem access alone is insufficient.
4. `LocalOperatorGate` verifies the 32-byte high-entropy operator secret
   against a trusted-only scrypt salt/verifier. The operator identity must
   differ from the requesting agent.
5. The sidecar approves the pending request in the **same trusted database**
   used by the running worker service. With `approve_and_execute`, it then
   verifies the separate worker credential, active lease and fixed job,
   reserves a signed one-time grant, and submits it to the root broker.
6. The root broker independently checks trusted peer UID, HMAC, lease,
   approval provenance, replay ledger and the allowlisted systemd job.

There is no operator credential issuance, arbitrary shell execution, signing
key access, or new capability exposed over the worker-facing stage socket.
Only `approve` and `approve_and_execute` are accepted; JSON keys and
request size are strictly bounded. Responses disclose only accepted/denied.

### Critical group separation

The sidecar must run under the trusted UID with a private effective group,
which owns the group-read permission on the root-owned 0640 broker key.
`agency.operator_service.verify_private_broker_group` checks that the
configured worker account does **not** belong to that private group. The
worker-facing service may have a *different* effective group to support its
stage socket. **Never put the worker in the broker signing-key group.**

A previous in-process dual-socket prototype was **not retained** because
combining the worker transport group with the broker key group could have
exposed HMAC signing material. The existing service lifecycle and CLI were
restored unchanged.

### Other restrictions

- Root UID is the only accepted operator peer in the initial implementation.
  A compromised root account is outside this model's isolation guarantee.
- Operator secret and worker credential/lease are never passed as CLI options
  or logged. Provisioning is interactive and stores only a 0600 verifier.
- No remote HTTP access, automatic credential issuance, general-purpose
  agent tools, MFA, or distributed brute-force rate limiter.
- Any failed approval, lease check, HMAC validation or broker request denies.
  A failed execution attempt may leave a consumed grant; do not retry blindly.

## Isolated acceptance (does not touch production)

On the **development checkout** on the VPS:

```bash
cd /root/Hermes-Agency
git pull --ff-only origin development/foundation
python3 -m unittest discover -s tests -q
echo "TEST_EXIT_CODE=$?"
bash deploy/test_supervised_integration.sh
echo "OPERATOR_RUNTIME_EXIT_CODE=$?"
systemctl is-active hermes-agency.service
```

The script creates independent temporary systemd units for the root broker
and the trusted operator sidecar, using a throwaway database, broker key,
operator verifier and test-only operator secret. It checks that:

- Worker cannot reach broker or operator socket.
- Wrong root-operator secret leaves the approval pending and the broker ledger
  unchanged.
- Correct root-operator secret causes the existing approval to be consumed
  after a real fixed `noop` job finishes through the signed broker.
- Unused grants signed before HMAC rotation are rejected; new grants succeed.
- Ledger ends with exactly three completed isolated jobs, no extra entries.
- The actual `hermes-agency.service` remains active.

The acceptance units deliberately use temporary paths, `PrivateTmp=no`,
`ProtectHome=no`, and test-specific `ReadWritePaths`. Passing acceptance
does not prove full production unit equivalence or that the running service
has been upgraded to this code. No test should replace production state.

## Manual production preparation (NOT authorized by this document)

Only after operator review and explicit deployment approval:

1. Verify the installed code, protected trusted database/key paths, and
   systemd unit settings. Use the original trusted-UID account and its
   **private** primary group for the separate operator sidecar.
2. Provision a distinct socket directory such as
   `/run/hermes-operator`, trusted-UID-owned, mode 0700, separate from
   `/run/hermes-agency`. Handle its recreation after reboot via the
   supervisor. Do not chown or chmod the existing worker directory.
3. Run `python3 -m agency.operator_provision --path ABSOLUTE_VERIFIER_PATH
   --identity operator` **as the trusted UID** after installing tested code.
   The command prompts twice for a 64-character lowercase hex secret
   generated with a cryptographically secure random source. Keep it in an
   operator-controlled password manager; never paste it into a chat, Git
   commit, environment variable or shell history.
4. Install an independent systemd operator sidecar using the installed
   audited version of `agency.operator_service`; do **not** change the
   existing `hermes-agency.service` arguments. Required sidecar arguments:

```text
--state-dir /var/lib/hermes-agency
--database /var/lib/hermes-agency/agency.db
--key-dir /var/lib/hermes-agency/keys
--secret-file /var/lib/hermes-agency/keys/signing.key
--operator-socket /run/hermes-operator/operator.sock
--operator-verifier ABSOLUTE_VERIFIER_PATH
--broker-key /etc/hermes-broker/signing.key
--broker-socket /run/hermes-broker/broker.sock
--worker-user hermes-worker
```

Paths above are illustrative and must be checked against the **actual**
installed service and broker; never infer credential paths from this document.
The sidecar is a separate service using `User=hermes-trusted` and its private
group, not the group that authorizes worker stage socket connections.

The root operator uses the interactive client; no secret is passed via argv:

```bash
python3 -m agency.operator_client \
  --socket /run/hermes-operator/operator.sock \
  --approval-id EXISTING_PENDING_APPROVAL_ID --action approve

python3 -m agency.operator_client \
  --socket /run/hermes-operator/operator.sock \
  --approval-id EXISTING_PENDING_APPROVAL_ID \
  --action approve_and_execute --task-id EXISTING_TASK_ID --job noop
```

The execution action prompts privately for the **valid worker credential
and active lease token** already obtained from trusted authentication. It
does not mint them.

## Rollback

Stop only the optional operator sidecar and optional root broker, preserving
the primary worker service, private trusted database, and immutable audit
ledger. Removing the sidecar must not modify worker socket permissions,
agent approval records, or production credentials. Confirm the existing
worker service still responds normally before considering activation complete.

**No production activation, secret provisioning, service restart or live
operator approval has been performed by the development changes.**
