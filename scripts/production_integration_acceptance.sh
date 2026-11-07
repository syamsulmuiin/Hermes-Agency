#!/usr/bin/env bash
# One-command production integration PREPARATION acceptance; never cuts over production.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PIN=912dce6aef6b
CANDIDATE="/opt/hermes-fenced-$PIN"
for unit in hermes-agency.service hermes-signed-broker.service hermes-operator-sidecar.service; do
  if [[ "$(systemctl is-active "$unit")" != active ]]; then
    echo "PRODUCTION_HEALTH=FAIL"
    exit 1
  fi
done
echo "PRODUCTION_HEALTH=PASS"
python3 -m unittest discover -s tests -q
python3 -m agency.fenced_final_manifest_audit
systemd-analyze verify deploy/systemd/hermes-fenced-broker-candidate.service deploy/systemd/hermes-fenced-recovery-candidate.service
git cat-file -e "$PIN^{commit}"
[[ "$(git rev-parse --short=12 "$PIN")" == "$PIN" ]] || { echo "PIN_PROVENANCE=FAIL"; exit 1; }
[[ -d /run/hermes-staging ]] || install -d -m 0700 /run/hermes-staging
if [[ ! -e "$CANDIDATE" ]]; then
  mkdir "$CANDIDATE"
  git archive "$PIN" | tar -x -C "$CANDIDATE"
fi
TMP="$(mktemp -d /run/hermes-staging/pincheck.XXXXXX)"
trap 'rm -rf -- "$TMP"' EXIT
git archive "$PIN" | tar -x -C "$TMP"
diff -qr "$TMP" "$CANDIDATE" >/dev/null
echo "PIN_PROVENANCE=PASS"
python3 -m agency.isolated_candidate_acceptance --execute --deployed "$CANDIDATE"
set +e
python3 -m agency.production_state_readonly_audit
audit_code=$?
set -e
if [[ "$audit_code" -eq 2 ]]; then
  echo "PRODUCTION_STATE_READINESS=NO_GO_EXPECTED"
elif [[ "$audit_code" -eq 0 ]]; then
  echo "PRODUCTION_STATE_READINESS=PASS"
else
  echo "PRODUCTION_STATE_AUDIT=ERROR"
  exit "$audit_code"
fi
for unit in hermes-agency.service hermes-signed-broker.service hermes-operator-sidecar.service; do
  [[ "$(systemctl is-active "$unit")" == active ]] || { echo "PRODUCTION_HEALTH_AFTER=FAIL"; exit 1; }
done
echo "PRODUCTION_HEALTH_AFTER=PASS"
echo "PREPARATION_ACCEPTANCE=PASS"
echo "PRODUCTION_CUTOVER_EXECUTED=NO"
echo "PRODUCTION_CUTOVER_AUTHORIZED=NO"
