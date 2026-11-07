#!/usr/bin/env bash
# Read-only production package compatibility staging; never touches production.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROD="${PRODUCTION_PACKAGE:-/opt/hermes-agency/agency}"
[[ -d "$PROD" ]] || { echo "Production package directory missing" >&2; exit 1; }
BASE="$(mktemp -d /tmp/hermes-runtime-staging.XXXXXXXX)"
trap 'rm -rf -- "$BASE"' EXIT
mkdir -p "$BASE/agency"
# Copy Python source only: no databases, credentials, sockets, or runtime state.
find "$PROD" -maxdepth 1 -type f -name '*.py' -exec cp -- '{}' "$BASE/agency/" \;
# Explicit opt-in runtime additions, not test-only modules.
RUNTIME=(
  trusted_execution.py trusted_broker_adapter.py broker_grants.py
  signed_broker_service.py supervised_broker.py systemd_broker.py
  systemd_jobs.py operator_control.py operator_service.py
  operator_provision.py operator_client.py
)
for file in "${RUNTIME[@]}"; do
  [[ -f "$ROOT/agency/$file" ]] || { echo "Missing development file: $file" >&2; exit 1; }
  cp -- "$ROOT/agency/$file" "$BASE/agency/$file"
done
PYTHONPATH="$BASE" python3 -I - "$BASE" <<'PY'
import importlib
import pathlib
import sys
base = pathlib.Path(sys.argv[1]).resolve()
# -I ignores PYTHONPATH; explicitly add staging root, never the development checkout.
sys.path.insert(0, str(base))
names = [
    "single_vps_service", "service_lifecycle", "private_state",
    "trusted_execution", "trusted_broker_adapter", "broker_grants",
    "signed_broker_service", "supervised_broker", "systemd_broker",
    "systemd_jobs", "operator_control", "operator_service",
    "operator_provision", "operator_client",
]
for name in names:
    module = importlib.import_module("agency." + name)
    origin = pathlib.Path(module.__file__).resolve()
    if not origin.is_relative_to(base):
        raise RuntimeError("Module loaded outside staging: " + name)
    print("STAGING_IMPORT_PASS " + name)
print("STAGING_IMPORT_EXIT_CODE=0")
PY
echo "PRODUCTION_UNCHANGED=YES"
