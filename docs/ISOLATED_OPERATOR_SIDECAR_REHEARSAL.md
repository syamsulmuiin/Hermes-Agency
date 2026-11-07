# Isolated operator-sidecar routing rehearsal

Status: DESIGN / NOT EXECUTED. Production cutover: NO-GO.

## Objective
Prove the complete **root operator IPC -> trusted non-root sidecar -> signed fenced candidate broker -> owned systemd unit -> independent recovery** chain. The prior `agency.isolated_candidate_acceptance` proves operator authentication and signed grants but **does not launch `agency.operator_service` or send an actual Unix operator IPC request**. Never label that earlier test a full sidecar E2E.

## Non-negotiable isolation
- Do not change, restart, stop, reload, enable, or reconfigure `hermes-agency.service`, `hermes-signed-broker.service`, or `hermes-operator-sidecar.service`.
- All SQLite files, signing keys, verifier files, sockets, journals, hold markers, and test jobs must be newly created under a unique `/run/hermes-staging/<run-id>`. Never use `/var/lib/hermes-agency`, `/var/lib/hermes-broker`, `/etc/hermes-broker/signing.key`, or the legacy socket.
- Run broker/recovery as disposable systemd units from an immutable `/opt/hermes-fenced-<12hex>` snapshot. Keep the effective sandbox gate for both units.
- Run sidecar under a distinct non-root trusted UID and **private primary group**. The staging signing key must be root:trusted-private-group, 0640, 64 bytes; its parent must be traversable by that group. Use the same permission verification functions as production.
- Operator socket must live in a 0700 trusted-owned directory and be contacted by a real root process over Unix IPC (SO_PEERCRED). A worker identity must not be able to connect or read signing material.
- Rehearsal must fail closed and clean up only its own disposable units, sockets and staging directory. Never remove pre-existing paths.

## Required sequence (implementation acceptance contract)
1. Pin candidate snapshot and verify clean identity and isolated staging layout.
2. Provision an isolated trusted DB, credential secret, operator verifier (scrypt), signing key and worker identity. Create a pending task, lease, credential and approval **without approving it**.
3. Start fenced broker and independent recovery units; verify effective systemd sandbox and candidate socket.
4. Start the actual `agency.operator_service` executable as a trusted-UID staging sidecar with isolated `--state-dir`, `--database`, `--key-dir`, `--secret-file`, `--operator-socket`, `--operator-verifier`, `--broker-key`, `--broker-socket`, and `--worker-user`. Verify it binds only its private socket and has the intended effective UID/GID.
5. Send a malformed or wrong-secret operator request: require `denied` and no broker execution. Send the valid `approve_and_execute` request through root Unix IPC: require `accepted`, signed grant consumed once and a systemd-owned `noop` job exit 0. Repeat the request: require denial/no duplicate execution.
6. Create a separate approved hold job through the same operator IPC route, SIGKILL the fenced broker, verify pending startup gate stays closed and PID 1 independent recovery stops the owned unit. Restart disposable broker only after recovery and verify recovery gate opens.
7. Stop only staging services and verify their transient unit files, sockets, journals and staging secrets are removed. Confirm all **three** original production services remain active with unchanged effective ExecStart/socket routing. Check no candidate unit is enabled.
8. Produce explicit machine-readable PASS/FAIL for sidecar IPC, operator authentication, signed grant, replay denial, lease fence, SIGKILL recovery, disposable rollback and production unchanged. Do not mark PASS based on source inspection alone.

## Current evidence and blockers
- Prior VPS staging test: `PERSISTENT_CANDIDATE_ISOLATED_E2E=PASS`, effective sandbox PASS, recovery PASS, disposable cleanup PASS. **No actual sidecar IPC was exercised**.
- Production sidecar is active as `hermes-trusted:hermes-trusted` and points to `/run/hermes-broker/broker.sock`. Fenced socket absent. Existing production route must remain unchanged during rehearsal.
- Candidate manifest still pins `/opt/hermes-fenced-377abe8b948b`, not latest tested snapshot. Production recovery journal absent; neither fact authorizes production writes.
- Production cutover and production rollback remain untested; no cutover authorization.

## Next implementation
Extend the existing isolated candidate acceptance harness with an opt-in **actual sidecar IPC** scenario and dedicated regression tests, rather than substituting synthetic direct signed-grant submission. First run unit tests, then perform the root VPS rehearsal against a fresh pinned snapshot. Only after full sidecar E2E PASS prepare a separately approved production cutover and rollback plan.
