#!/usr/bin/env bash
# Opt-in isolated acceptance. Requires root, systemd, trusted+worker users.
# Does not install or enable a persistent service or alter production state.
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo "Root required" >&2; exit 1; }
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
TRUSTED_USER="${TRUSTED_USER:-hermes-trusted}"
WORKER_USER="${WORKER_USER:-hermes-worker}"
TUID="$(id -u "$TRUSTED_USER")"
TGID="$(id -g "$TRUSTED_USER")"
WUID="$(id -u "$WORKER_USER")"
if id -G "$WORKER_USER" | tr ' ' '\n' | grep -qx "$TGID"; then
  echo "Worker belongs to trusted primary group; refusing" >&2; exit 1
fi
BASE="$(mktemp -d /tmp/hermes-supervised-e2e.XXXXXXXX)"
UNIT="hermes-broker-accept-${BASE##*.}"
OPUNIT="hermes-operator-accept-${BASE##*.}"
cleanup() {
  systemctl stop "$OPUNIT.service" >/dev/null 2>&1 || true
  systemctl reset-failed "$OPUNIT.service" >/dev/null 2>&1 || true
  systemctl stop "$UNIT.service" >/dev/null 2>&1 || true
  systemctl reset-failed "$UNIT.service" >/dev/null 2>&1 || true
  rm -rf -- "$BASE"
}
trap cleanup EXIT
chmod 0711 "$BASE"
install -d -m 0710 -o root -g "$TGID" "$BASE/socket"
install -d -m 0700 -o "$TUID" -g "$TGID" "$BASE/trusted"
install -d -m 0700 -o root -g root "$BASE/ledger"
install -d -m 0710 -o root -g "$TGID" "$BASE/keys"
install -d -m 0755 -o root -g root "$BASE/app"
cp -a "$ROOT/agency" "$BASE/app/"
chmod -R a+rX "$BASE/app/agency"
python3 - "$BASE" "$TGID" <<'PY'
import os, sys
from agency.signed_broker_service import provision_broker_key
from agency.systemd_broker import initialize_ledger
base, gid = sys.argv[1], int(sys.argv[2])
provision_broker_key(base + "/keys/broker.key", gid)
initialize_ledger(base + "/ledger/ledger.sqlite")
PY
# Credential key is separate and accessible only to the trusted process.
python3 - "$BASE" "$TUID" "$TGID" <<'PY'
import os, sys
base, uid, gid = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
p = base + "/trusted/credential.key"
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
try:
    os.fchown(fd, uid, gid)
    os.write(fd, os.urandom(64))
finally:
    os.close(fd)
PY
SOCK="$BASE/socket/broker.sock"
DB="$BASE/trusted/agency.sqlite"
KEY="$BASE/keys/broker.key"
LEDGER="$BASE/ledger/ledger.sqlite"
# The test-only unit is started by systemd-run, not by a shell background job.
systemd-run --system --unit="$UNIT" --collect \
  --working-directory="$BASE/app" \
  --property=Type=exec --property=NoNewPrivileges=yes \
  --property=ProtectHome=no --property=ProtectSystem=strict \
  --property="ReadWritePaths=$BASE" \
  --property=PrivateTmp=no --property=RestrictAddressFamilies=AF_UNIX \
  --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes \
  --property=ProtectKernelLogs=yes --property=ProtectControlGroups=yes \
  --property=ProtectClock=yes --property=PrivateDevices=yes \
  --property=RestrictSUIDSGID=yes --property=LockPersonality=yes \
  --property=RestrictRealtime=yes --property=SystemCallArchitectures=native \
  /usr/bin/env PYTHONPATH="$BASE/app" /usr/bin/python3 -m agency.supervised_broker \
  --socket "$SOCK" --trusted-user "$TRUSTED_USER" \
  --ledger "$LEDGER" --trusted-db "$DB" --key "$KEY"
for _ in $(seq 1 80); do
  [[ -S "$SOCK" ]] && break
  sleep 0.1
done
[[ -S "$SOCK" ]] || { echo "Broker startup failed; unit journal:" >&2; journalctl -u "$UNIT" -n 30 --no-pager; exit 1; }
[[ "$(stat -c '%a:%u:%g' "$SOCK")" == "660:0:$TGID" ]] || exit 1
if runuser -u "$WORKER_USER" -- python3 -c 'import socket,sys;s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1])' "$SOCK" >/dev/null 2>&1; then
  echo "SECURITY FAILURE: worker connected" >&2; exit 1
fi
runuser -u "$TRUSTED_USER" -- /usr/bin/env PYTHONPATH="$BASE/app" /usr/bin/python3 -m agency.supervised_integration_client \
  --database "$DB" --credential-key "$BASE/trusted/credential.key" \
  --broker-key "$KEY" --socket "$SOCK"
OLD_GRANT="$BASE/trusted/unused-old-grant.json"
runuser -u "$TRUSTED_USER" -- /usr/bin/env PYTHONPATH="$BASE/app" /usr/bin/python3 -m agency.supervised_integration_client \
  --database "$DB" --credential-key "$BASE/trusted/credential.key" \
  --broker-key "$KEY" --socket "$SOCK" --prepare-path "$OLD_GRANT"
python3 - "$KEY" "$TUID" "$TGID" <<'PY'
import sys
from agency.broker_key_rotation import rotate_broker_key
rotate_broker_key(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
PY
# Verify rejection while old grant is unexpired and its lease is still live.
runuser -u "$TRUSTED_USER" -- /usr/bin/env PYTHONPATH="$BASE/app" /usr/bin/python3 - "$SOCK" "$OLD_GRANT" <<'PY'
import json, sys, time
from pathlib import Path
from agency.signed_broker_service import submit_signed_grant
envelope = json.loads(Path(sys.argv[2]).read_text())
assert time.time() < envelope["claims"]["exp"], "Old grant expired before rotation check"
try:
    response = submit_signed_grant(sys.argv[1], envelope)
except (PermissionError, OSError):
    print("unused_pre_rotation_grant_rejected=PASS")
else:
    raise AssertionError("Old grant accepted: " + repr(response))
PY
python3 - "$LEDGER" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    count = db.execute("SELECT COUNT(*) FROM signed_grant_consumptions").fetchone()[0]
assert count == 1, ("Rejected old grant reached ledger", count)
print("rejected_grant_no_execution=PASS")
PY
# New key must still authorize a fresh real approval from the trusted UID.
runuser -u "$TRUSTED_USER" -- /usr/bin/env PYTHONPATH="$BASE/app" /usr/bin/python3 -m agency.supervised_integration_client \
  --database "$DB" --credential-key "$BASE/trusted/credential.key" \
  --broker-key "$KEY" --socket "$SOCK"
# Start an isolated copy of the REAL trusted service with opt-in operator IPC.
# The live production hermes-agency.service is not touched.
WORKER_GID="$(id -g "$WORKER_USER")"
TRUSTED_GROUP="$(id -gn "$TRUSTED_USER")"
install -d -m 0710 -o "$TUID" -g "$WORKER_GID" "$BASE/worker-socket"
install -d -m 0700 -o "$TUID" -g "$TGID" "$BASE/operator"
install -d -m 0700 -o "$TUID" -g "$TGID" "$BASE/trusted/keys"
chown "$TUID:$TGID" "$DB"
chmod 0600 "$DB"
python3 - "$BASE/trusted/operator_verifier.json" "$TUID" "$TGID" <<'PY'
import json, os, sys
from agency.operator_auth import LocalOperatorGate
path, uid, gid = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
# Test-only ephemeral secret; NEVER use this value outside this acceptance.
salt, verifier = LocalOperatorGate.provision(bytes.fromhex("4f" * 32))
record = {"identity": "operator", "salt_hex": salt.hex(), "verifier_hex": verifier.hex()}
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
try:
    os.fchown(fd, uid, gid)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        fd = -1
        json.dump(record, output)
finally:
    if fd >= 0:
        os.close(fd)
PY
OPSOCK="$BASE/operator/operator.sock"
systemd-run --system --unit="$OPUNIT" --collect \
  --working-directory="$BASE/app" \
  --property=Type=exec --property="User=$TRUSTED_USER" \
  --property="Group=$TRUSTED_GROUP" --property=NoNewPrivileges=yes \
  --property=ProtectHome=no --property=PrivateTmp=no \
  --property=ProtectSystem=strict --property="ReadWritePaths=$BASE" \
  --property=RestrictAddressFamilies=AF_UNIX \
  /usr/bin/env PYTHONPATH="$BASE/app" /usr/bin/python3 -m agency.single_vps_service \
  --forever --socket "$BASE/worker-socket/trusted.sock" \
  --state-dir "$BASE/trusted" --database "$DB" \
  --key-dir "$BASE/trusted/keys" --client-gid "$WORKER_GID" \
  --allow-uid "$WUID" --secret-file "$BASE/trusted/credential.key" \
  --operator-socket "$OPSOCK" \
  --operator-verifier "$BASE/trusted/operator_verifier.json" \
  --broker-key "$KEY" --broker-socket "$SOCK"
for _ in $(seq 1 80); do
  [[ -S "$OPSOCK" ]] && break
  sleep 0.1
done
[[ -S "$OPSOCK" ]] || { echo "Operator socket startup failed" >&2; journalctl -u "$OPUNIT" -n 30 --no-pager; exit 1; }
[[ "$(stat -c '%a:%u:%g' "$OPSOCK")" == "600:$TUID:$TGID" ]] || exit 1
if runuser -u "$WORKER_USER" -- python3 -c 'import socket,sys;s=socket.socket(socket.AF_UNIX);s.connect(sys.argv[1])' "$OPSOCK" >/dev/null 2>&1; then
  echo "SECURITY FAILURE: worker reached operator socket" >&2; exit 1
fi
echo "worker_operator_socket_denied=PASS"
OPREQUEST="$BASE/trusted/pending-operator.json"
runuser -u "$TRUSTED_USER" -- /usr/bin/env PYTHONPATH="$BASE/app" /usr/bin/python3 -m agency.supervised_integration_client \
  --database "$DB" --credential-key "$BASE/trusted/credential.key" \
  --broker-key "$KEY" --socket "$SOCK" \
  --prepare-operator-path "$OPREQUEST"
python3 - "$OPSOCK" "$OPREQUEST" "$DB" "$LEDGER" <<'PY'
import json, socket, sqlite3, sys
from pathlib import Path
sock, reqpath, dbpath, ledgerpath = sys.argv[1:]
fixture = json.loads(Path(reqpath).read_text())
def send(secret):
    payload = dict(fixture, operator_secret_hex=secret)
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(5)
        client.connect(sock)
        client.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        client.shutdown(socket.SHUT_WR)
        data = client.recv(128)
    return json.loads(data)
assert send("00" * 32) == {"status": "denied"}, "Invalid operator secret accepted"
with sqlite3.connect(dbpath) as db:
    row = db.execute("SELECT status FROM approvals WHERE id=?", (fixture["approval_id"],)).fetchone()
assert row == ("pending",), ("Invalid operator secret mutated approval", row)
with sqlite3.connect(ledgerpath) as db:
    count = db.execute("SELECT COUNT(*) FROM signed_grant_consumptions").fetchone()[0]
assert count == 2, ("Bad operator secret consumed broker grant", count)
print("invalid_operator_secret_denied=PASS")
assert send("4f" * 32) == {"status": "accepted"}, "Valid root operator failed"
with sqlite3.connect(dbpath) as db:
    row = db.execute("SELECT status,reviewer FROM approvals WHERE id=?", (fixture["approval_id"],)).fetchone()
assert row == ("consumed", "operator"), ("Operator approval not consumed", row)
with sqlite3.connect(ledgerpath) as db:
    rows = db.execute("SELECT status,COUNT(*) FROM signed_grant_consumptions GROUP BY status").fetchall()
assert rows == [("completed", 3)], ("Operator job not completed", rows)
print("authenticated_operator_to_systemd=PASS")
PY
systemctl is-active --quiet "$OPUNIT.service"
systemctl is-active --quiet "$UNIT.service"
python3 - "$LEDGER" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    rows = db.execute("SELECT status,COUNT(*) FROM signed_grant_consumptions GROUP BY status").fetchall()
assert rows == [("completed", 3)], rows
print('supervised_systemd=PASS worker_denied=PASS key_rotated_new_grants=PASS operator_peer_denied=PASS authenticated_operator=PASS ledger=PASS')
PY
