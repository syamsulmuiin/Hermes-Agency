# Fenced broker production integration preparation

Status: **NO-GO / staging-only**. No production cutover is authorized.

## Verified baseline (operator-reported, 2026-11-07)
- 316 unit tests OK (1 skipped).
- Pinned staging acceptance at commit `912dce6aef6b`: `ACCEPTANCE_EXIT_CODE=0`, sidecar-originated held job active, broker SIGKILL, pending startup gate, independent systemd recovery, restart and disposable rollback all PASS.
- Three existing production services remained active.
- Production sidecar currently targets `/run/hermes-broker/broker.sock`, **not** fenced candidate socket. Both existing broker and sidecar have transient `90-startup-test.conf` overrides setting `Restart=no`.
- Production unit configuration was inspected from user-supplied systemctl output; no live cutover or production recovery test has been performed.

## Prepared candidate manifests
- Both candidate manifests and static manifest gate pin `/opt/hermes-fenced-912dce6aef6b`. This directory **must be created from exactly that Git commit** if absent; do not use an arbitrary current HEAD archive.
- Candidate socket remains `/run/hermes-broker/fenced-candidate.sock`; no production sidecar or broker routing changes.
- Broker requires and starts after the independent recovery oneshot; its startup gate denies pending ownership. `ExecStopPost` and `OnFailure` are additional independent recovery triggers.
- These manifest files are templates, not installed systemd units. Their real `/var/lib` paths are **production paths**; never start them in parallel with the current production broker or against live journal/ledger as an isolated test.

## Safe staging validation on VPS (no production service changes)
Run from `/root/Hermes-Agency`:
```bash
git pull --ff-only origin development/foundation
python3 -m py_compile agency/fenced_final_manifest_audit.py agency/isolated_candidate_acceptance.py agency/isolated_sidecar_rehearsal.py
python3 -m unittest discover -s tests -q
python3 -m agency.fenced_final_manifest_audit
systemd-analyze verify deploy/systemd/hermes-fenced-broker-candidate.service deploy/systemd/hermes-fenced-recovery-candidate.service
PIN=912dce6aef6b
git cat-file -e "$PIN^{commit}" || { echo "Missing pinned commit"; exit 1; }
git rev-parse --short=12 "$PIN"
# Create only the missing, immutable candidate directory; do not overwrite existing contents.
if [ ! -e "/opt/hermes-fenced-$PIN" ]; then
  mkdir "/opt/hermes-fenced-$PIN" || exit 1
  git archive "$PIN" | tar -x -C "/opt/hermes-fenced-$PIN" || exit 1
fi
# Verify the exact pinned source bytes against git before using the snapshot.
```
Then verify the exact pinned snapshot against the archived commit and run isolated acceptance:
```bash
PIN=912dce6aef6b
TMP=$(mktemp -d /run/hermes-staging/pincheck.XXXXXX) || exit 1
git archive "$PIN" | tar -x -C "$TMP" || exit 1
diff -qr "$TMP" "/opt/hermes-fenced-$PIN"
RESULT=$?
rm -rf -- "$TMP"
test "$RESULT" -eq 0 || exit 1
python3 -m agency.isolated_candidate_acceptance --execute --deployed "/opt/hermes-fenced-$PIN"
```
**Important:** the pinned snapshot must exist before acceptance. The acceptance harness itself creates disposable `/run/hermes-staging` paths and temporary units, and must exit 0 with all sidecar/SIGKILL/recovery/rollback PASS markers. Confirm all three production units remain active.

## Cutover prerequisites (not execution instructions)
1. Explicit user approval for a scheduled maintenance window, service interruptions, and a tested rollback.
2. Verified backup/restore procedure for trusted SQLite database, broker ledger, ownership journal, signing keys, and service units; do not disclose secrets in logs.
3. Audit whether existing broker ledger and fenced broker ledger schemas are compatible, whether any pending grants/owned units exist, and how to quiesce new approvals safely. Do **not** share a live ledger between two brokers.
4. Define an exclusive writer/consumer transition: stop admitting new jobs, drain or independently recover pending units, verify journal gate, stop old broker, then start fenced broker. Never run old and new brokers concurrently against the same live state.
5. Review and explicitly decide what to do with temporary `Restart=no` drop-ins; preserve until approved change window.
6. Sidecar currently points to `broker.sock`; a coordinated, audited routing change is required, with effective permissions and peer-credential verification. The candidate-only socket must not be silently substituted.
7. Verify independent recovery works on the target host with the actual production filesystem and permissions under a controlled maintenance rehearsal; the staging test alone is not proof.
8. Define objective abort conditions: failed startup gate, pending unit, inconsistent ledger, missing socket, sidecar authorization failure, or any failed health check.

## Rollback invariants (design; not yet tested on production)
- Fail closed: no new job may be accepted while an unverified owned unit remains pending.
- Before returning to legacy broker, independently stop and verify all candidate-owned units and persist verified ownership state. Never delete the journal to bypass the gate.
- Preserve signed-grant consumption history and approvals; do not reset ledgers, lease tokens, or replay protection.
- Restore the prior service configuration and socket routing only after verifying the broker is stopped and recovery complete; then verify three services and run read-only replay-denial/health checks.
- Retain an immutable copy of prior manifests and a documented, authorized restoration path.

## GO/NO-GO
**NO-GO for production cutover** until snapshot provenance, staged acceptance on the pinned snapshot, runtime effective manifests, real database compatibility, no-dual-broker transition, production-safe backup/rollback, and explicit authorization all pass. A successful static audit or staging rehearsal is not a production deployment authorization.

## Complete handover protocol (design only; no production action performed)

**Admission freeze.** The operator sidecar is currently configured to send signed grants to `/run/hermes-broker/broker.sock`. A reliable freeze must be enforced at the operator admission boundary, not by merely changing the socket path: already authorized requests may be in flight. A production cutover needs a reviewed, explicitly authorized quiesce mechanism and proof of zero active admissions. No such mechanism has yet been verified in production. Do not assume stopping the broker alone drains work.

**Exclusive state ownership.** Legacy and fenced brokers MUST NOT be running against the same live ledger/trusted DB. During an approved maintenance window: freeze admission; wait for or safely abort in-flight requests; stop the old broker and verify its process/socket are gone; take a consistent SQLite backup; validate the replay ledger and outstanding approvals; bootstrap the missing ownership journal with `agency.fenced_unit_journal._connect` only under exclusive, root-owned private directory conditions; verify journal is empty and `require_recovered` passes; verify permissions; start recovery oneshot; verify startup gate; start the new broker; then switch the operator sidecar's broker socket configuration under reviewed unit changes; verify peer credentials and replay denial before unfreezing admission. These are invariants and a design sequence, NOT a copy/paste production script.

**Replay preservation.** Preserve every row of `signed_grant_consumptions` if present, including failed/started rows, and never reuse a grant ID. The observed production ledger contains only `approvals` and `audit` with zero approvals; signed consumption table is absent. The existing implementation creates the signed consumption table lazily on first grant. A migration must not erase, truncate, or recreate an existing ledger in place. Do not equate zero legacy approvals with proof that no signed grants are in flight. Validate against the trusted DB and operator queue.

**Recovery/rollback.** If any fenced unit is pending or systemd stop verification is uncertain, keep admission frozen and fail closed. Recovery service must stop/verify each owned unit before marking it verified. Restore old unit files, socket routing and restart policy only after the fenced broker has stopped, all candidate-owned units are verified stopped, and ledger/replay history remains intact. Avoid restoring an older ledger backup over newly consumed grants; that would reopen replay. Prefer retaining the current ledger and reversing only service routing after compatibility verification. An authorized rollback must include a no-replay test, operator authorization test, and all three service health checks.

**Explicit blockers from read-only VPS audit.** Source ownership journal absent; signed-grant consumption table absent; zero legacy approvals; copy-only rehearsal passed; production service health 3/3. The audit tool returns `PRODUCTION_CUTOVER_STATE_GATE=NO_GO` with exit code 2. Neither an actual admission freeze nor a live exclusive handover/rollback has been tested. There is no basis to claim production GO.

**Single-command preparation acceptance:** `bash scripts/production_integration_acceptance.sh` runs the unit suite, static manifest check, systemd syntax verification, pinned snapshot provenance, isolated real-systemd crash acceptance, read-only SQLite snapshot/copy rehearsal, and pre/post production health. It does **not** stop/restart/reconfigure production or perform a real cutover. `PREPARATION_ACCEPTANCE=PASS` means the preparation suite passed, not that production is ready to switch.
