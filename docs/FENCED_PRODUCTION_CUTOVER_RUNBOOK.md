# Production fenced broker cutover — safety gate and rollback

Status: **BLOCKED pending live sandbox and caller-path validation**. This is an operator runbook, not permission for an automated cutover.

## Verified evidence
- Isolated persistent candidate signed grants, replay denial, trusted SQLite lock, SIGKILL recovery and restart PASS.
- Real fenced runner mid-flight SIGKILL, startup gate and recovery PASS using an isolated test-only sleep job.
- Static candidate unit verification exit 0 and production services active.
- Existing production broker executes `agency.supervised_broker`; candidate runs `agency.fenced_broker_candidate` with a separate socket.

## Mandatory pre-cutover checks
1. Confirm the deployed, pinned revision at `/opt/hermes-agency` exists and is accessible to candidate service under `ProtectHome=yes`. The development checkout at `/root/Hermes-Agency` is not a valid substitute. Compare revision and Python imports from the service working directory.
2. Validate effective service sandbox with actual systemd unit, including `ProtectSystem=strict`, `ReadWritePaths`, trusted database read/write through the trusted UID, key access, root journal creation and socket permissions. Existing-path checks alone are insufficient.
3. Verify signed-grant issuer transport can target the fenced candidate socket without changing worker-facing protocols, signing material, approval semantics, replay ledger, or grant consumption. Exercise an isolated grant and an invalid/replayed grant.
4. Verify independent recovery unit ordering with a disposable deployment of the actual unit template and injected SIGKILL, stop failure, restart and fail-closed gate. The isolated acceptance fixture uses a different unit template.
5. Inspect pending owned units and active signed grants before any switch; require quiescence. Do not delete journal or ledger, rotate keys, or replay consumed grants.
6. Capture backups and verified restoration instructions for **unit files and application revision**, and a timestamped operational checkpoint for ledger and trusted DB. Never restore a stale DB/ledger snapshot over new production writes.

## Cutover decision
**No production switch until every check above passes and the operator approves the exact downtime window and commands.** Keep both `hermes-agency.service` and `hermes-signed-broker.service` unchanged while preparing.

## Rollback principles
- Stop *new admissions* before rollback; do not assume old broker is safe to start while fenced owned units are pending.
- Invoke independent recovery and verify every owned unit stopped and journal has no pending rows before considering the legacy broker.
- Preserve original broker unit, socket path, key, ledger and trusted DB; restore only the prior unit and application revision after verifying there are no in-flight jobs. Never roll back transactional DB state to an earlier snapshot.
- Verify both services active, authenticated signed-grant denial/replay behavior and no orphan units after rollback.
- If recovery or ownership verification fails, **do not restart the legacy broker**; leave admission blocked and escalate to manual investigation.

## Known blocker
The candidate unit has `WorkingDirectory=/opt/hermes-agency` and `ProtectHome=yes`. The operator currently runs development tests in `/root/Hermes-Agency`. An existing `/opt/hermes-agency` path was reported, but its revision, dependencies and runtime accessibility were not checked. No cutover has been executed.
