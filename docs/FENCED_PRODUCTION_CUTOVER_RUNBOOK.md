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

## Repository-controlled deployment parity gate
- Run `python3 -m agency.fenced_deployment_parity --source /root/Hermes-Agency --deployed /opt/hermes-agency` from the development checkout. A nonzero exit is a hard deployment blocker; the script does not copy or modify files.
- Deploy from a pinned GitHub revision to `/opt/hermes-agency` only after inspecting the existing deployment layout and preserving its service configuration. Never repair production by copying a single module from `/root` or replacing the entire `/opt` directory blindly.
- `systemd-analyze security` must be run against a real loadable unit name or correctly registered temporary unit; the previous relative-file invocation returned `Unit ... not found` and did not assess sandbox security. Static `systemd-analyze verify` exit 0 alone is insufficient.
- Every deployment fix must first be committed to `development/foundation`, then installed from that exact revision, and tested before a production cutover.

## Versioned, non-disruptive deployment preparation
- VPS inventory confirmed `/opt/hermes-agency` is a stale live deployment missing seven fenced modules. Do **not** overwrite it or redirect live units to `/root`.
- From the clean development checkout, run `python3 -m agency.fenced_prepare_deployment` for dry-run, then `python3 -m agency.fenced_prepare_deployment --execute` to create a *new*, pinned `/opt/hermes-fenced-<revision>` directory. The script clones committed Git content locally and never edits `/opt/hermes-agency`, unit files, keys, databases or live sockets. It does not activate services.
- The existing candidate unit manifest still targets `/opt/hermes-agency`; it must not be started against the new directory without an independently reviewed, GitHub-tracked staging manifest, sandbox validation and rollback checks.
- A prepared directory is not proof of sandbox or production readiness. Production cutover remains blocked.


## 2026-11-07 pinned candidate staging and final cutover decision procedure

Pinned VPS candidate: `/opt/hermes-fenced-377abe8b948b`, commit `377abe8b948b1857a5f1d5c3cfad7379d3a1a713`. Operator verified imports, isolated signed-grant/replay/lease/recovery E2E, real midflight SIGKILL and systemd sandbox imports (all exit 0). Both live services remained active. These are **not** proof of production manifest resource writes, PID1 ordering or caller routing.

### Read-only resource metadata test (safe before any staging activation)
From a clean `/root/Hermes-Agency` checkout, `git pull --ff-only origin development/foundation`, then:
```bash
python3 -m agency.fenced_resource_audit --deployed /opt/hermes-fenced-377abe8b948b --execute
echo "RESOURCE_AUDIT_EXIT_CODE=$?"
systemctl is-active hermes-agency.service hermes-signed-broker.service
```
This runs a disposable transient unit with the candidate sandbox settings and only checks metadata for live DB, ledger and signing key and directory existence. **No key bytes, DB contents or writes are accessed.** A PASS is **not** evidence of SQLite WAL writes, socket creation, private key read or trusted UID permissions. A failure must not be worked around by relaxing permissions or sandboxing.

### Required full integration acceptance (currently BLOCKED)
1. Create and review **GitHub-tracked** candidate staging units with unique names and dedicated test socket, journal, ledger, key and trusted DB; never bind `/run/hermes-broker/broker.sock` or share the production grant ledger. Use the pinned `/opt/hermes-fenced-*` working directory. The existing checked-in candidate manifest targets the stale `/opt/hermes-agency` and must not be installed as-is.
2. Validate exact effective sandbox (including writable journal/SQLite WAL and socket, key ownership and trusted UID), with negative tests for unauthorized peers. Verify that `ProtectSystem=strict` does not block trusted DB writes or required paths. No live grant should be consumed.
3. Test actual `Requires`/`After`/independent recovery unit, `ExecStopPost`, `OnFailure`, SIGKILL midflight, injected stop failure, concurrent recovery and restart fail-closed behavior using disposable staging units. Do not claim PID1 acceptance from transient import probes.
4. Validate signed-grant issuer/caller transport in isolation: exact socket target, peer UID, approval semantics, replay denial, signing key provenance, and no fallback to legacy path. Confirm active `single_vps_service` worker entrypoint actually exposes the operator-approved job flow before changing production routing.
5. Confirm ownership journal quiescence, in-flight grants, live unit inventory, operational checkpoint and explicit rollback commands; obtain operator approval for the exact cutover window. Until all gates pass, **do not stop/restart/enable/disable either live service**.

### Final cutover checklist (NOT AUTHORIZED TO EXECUTE)
- Record `systemctl cat`, `systemctl show`, `systemctl status`, active unit names and timestamps; retain immutable copies of previous unit files, exact application commit, socket names and permissions. Record backup/checkpoint metadata for ledger and trusted DB **without restoring stale copies over subsequent writes**.
- Confirm no pending fenced-owned units, no active jobs or unconsumed grants at switch time. Freeze new admissions using an operator-approved mechanism, never by silently discarding requests.
- Only after all acceptance tests and explicit approval: deploy reviewed version-pinned unit files, `systemd-analyze verify`, inspect effective security settings, `daemon-reload`, run independent recovery first, and confirm fail-closed gate before allowing candidate admissions. No automatic fallback to legacy broker.
- Verify approved-job signed grant end-to-end, invalid/replay denial, runtime watchdog, journaling and recovery. Confirm old socket is not accepting new work and no orphaned units exist.

### Rollback decision tree (NOT AUTHORIZED TO EXECUTE)
- If candidate startup or routing fails, **stop admissions first** and preserve all DB/ledger/journal files. Recover every owned transient unit using the independently tested recovery path and verify no pending records; do not assume broker termination stops its child units.
- If recovery is incomplete, corrupted or cannot verify unit state, keep admissions disabled and **do not restart legacy broker**. Escalate for manual forensic review.
- Only when ownership is quiescent, restore previous **unit configuration and application revision** (not transactional DB snapshots), reload systemd and restore the prior broker route under operator supervision.
- Revalidate both live services, signed-grant denial/replay, absence of orphan units and operational continuity. Preserve incident evidence and checkpoint revisions.

**Decision as of 2026-11-07: NO-GO for production cutover.** Remaining blockers are actual resource read/write integration, PID1 recovery unit ordering, and live caller routing; the read-only audit is only one bounded prerequisite.
