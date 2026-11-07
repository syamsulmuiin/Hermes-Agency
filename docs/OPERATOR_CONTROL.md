# Opt-in Local Operator Control (Development)

## Purpose and current status

This feature provides a **separate local Unix-domain operator control socket**
within an opt-in `agency.single_vps_service --forever` process. It is not
enabled in the existing production service, and the operator verifier and
broker runtime are **not** deployed automatically. Worker stage protocol,
worker group permissions, and the original trusted socket are unchanged.

The approved flow is:

1. A pre-existing workflow task and action approval are persisted by the trusted store.
2. A root operator process connects to the operator-only Unix socket.
3. The trusted listener checks the kernel `SO_PEERCRED` UID **before** reading the request.
4. The trusted process verifies the locally provisioned 32-byte operator secret
   against an owner-only scrypt verifier using `LocalOperatorGate`.
5. The trusted process decides the pending approval. For
   `approve_and_execute`, it then validates the separate worker credential,
   live lease, fixed-job allowlist, and approval provenance before reserving a
   single-use signed grant and contacting the root broker.
6. The root broker independently verifies the trusted UID, HMAC, grant lease,
   provenance, replay ledger and fixed-job policy, then executes an allowlisted
   systemd job.

No operator credential issuance, raw shell command, broker key material or
arbitrary tool invocation is available through the worker-facing stage socket.

## Constraints

- This initial channel permits **only UID 0** as operator peer. Root itself
  remains a privileged host identity; this adds application authorization
  against mistakes, not isolation from a compromised root account.
- A separate pre-created directory, **mode 0700 and owned by the non-root
  trusted UID**, must contain the operator socket. The socket uses mode 0600.
  Worker UIDs have no filesystem access, and the peer identity is also checked.
- The offline verifier is a single regular file, trusted-UID-owned, **0600**,
  with JSON keys `identity`, `salt_hex`, and `verifier_hex`. The operator
  secret is not stored in the verifier and must never be committed, transmitted
  over remote channels, included in shell history, or pasted into logs.
- Only `approve` and `approve_and_execute` are accepted. The latter requires
  a **pre-existing** valid worker credential and lease token, and can execute
  only a job from `agency.systemd_jobs.JOBS`.
- Requests are bounded to 12 KiB, have exact JSON field sets, and produce
  only `{"status":"accepted"}` or `{"status":"denied"}` responses.
- There is no HTTP access, no automatic host provisioning, and no fallback to
  an unauthenticated operator or direct worker-to-broker execution.
- The initial design has no global request-rate limiter or MFA. Limit the
  socket to root on the same host and use a high-entropy random secret.

## Acceptance before any production activation

On the VPS **development clone**, run:

```bash
cd /root/Hermes-Agency
git pull --ff-only origin development/foundation
python3 -m unittest discover -s tests -q
echo "TEST_EXIT_CODE=$?"
bash deploy/test_supervised_integration.sh
echo "OPERATOR_RUNTIME_EXIT_CODE=$?"
systemctl is-active hermes-agency.service
```

The isolated script uses temporary broker/trusted-service systemd units, a
throwaway SQLite database, a throwaway broker signing key and a **test-only**
operator secret. It must prove:

- worker denied at both operator and broker sockets;
- wrong operator secret rejected while approval remains pending and ledger unchanged;
- correct root operator secret approves a pending request and submits `noop`
  through the trusted process and signed broker;
- HMAC rotation rejects an unused pre-rotation grant and permits a fresh grant;
- three completed isolated ledger records with no unexpected entries;
- the installed `hermes-agency.service` remains active.

The transient trusted service has temporary `ReadWritePaths`,
`PrivateTmp=no` and `ProtectHome=no`, so this is **not** a production-unit
hardening equivalence test. Do not deploy if any acceptance step fails.

## Later production provisioning (requires separate authorization)

After runtime acceptance, deploy the audited code into the trusted service
installation and provision an operator directory **separate from**
`/run/hermes-agency`:

```text
/run/hermes-operator/      trusted UID, mode 0700
/run/hermes-operator/operator.sock  trusted UID, mode 0600 (listener creates it)
```

Store the protected verifier under the trusted-only keys directory, using
`python3 -m agency.operator_provision --path ABSOLUTE_VERIFIER_PATH
--identity operator` **under the trusted non-root identity**. The provisioner
prompts privately for the 64-hex-character random secret twice, writes only
scrypt salt/verifier, and refuses an existing destination. Record the secret in
an operator-controlled secret manager; do not share it with workers or GitHub.

Opt-in startup flags for the existing `--forever` trusted runner, in addition
to its existing required flags:

```text
--operator-socket /run/hermes-operator/operator.sock
--operator-verifier ABSOLUTE_VERIFIER_PATH
--broker-key /etc/hermes-broker/signing.key
--broker-socket /run/hermes-broker/broker.sock
```

All four flags are mandatory together. Without them, existing service behavior
remains unchanged. Start via supervised systemd only after confirming unit
filesystem permissions, broker availability, rollback and restart procedure.
The operator client is interactive and never takes secrets as CLI arguments:

```bash
python3 -m agency.operator_client \
  --socket /run/hermes-operator/operator.sock \
  --approval-id EXISTING_PENDING_APPROVAL_ID \
  --action approve

python3 -m agency.operator_client \
  --socket /run/hermes-operator/operator.sock \
  --approval-id EXISTING_PENDING_APPROVAL_ID \
  --action approve_and_execute \
  --task-id EXISTING_TASK_ID --job noop
```

The second command prompts privately for both a pre-authenticated worker
credential and a valid active worker lease token, then records approval and
attempts the allowlisted broker job. Do not expose either through agent tools.

**Rollback:** disable the four opt-in flags and restore the previous trusted
service unit/code if deployment validation fails. Never remove or replace
production SQLite data or broker ledger while rolling back. A real rollback
must be approved and executed by the VPS operator, not by this document.
