"""Read-only staging fixture boundary audit; no processes or systemd calls.

This checks the pinned paths and existing harness wiring, not runtime isolation.
"""
import inspect
import pathlib

from . import combined_real_socket_cutover_e2e as combined
from . import real_candidate_socket_replay_e2e as replay
from . import isolated_systemd_cutover_test as cutover
from . import fenced_broker_candidate as candidate
from . import operator_service

STAGING_BASE = "/run/hermes-staging"
PRODUCTION_PATHS = (
    "/var/lib/hermes-agency",
    "/var/lib/hermes-broker",
    "/etc/hermes-broker",
    "/run/hermes-broker",
    "/run/hermes-operator",
)


def audit():
    if replay.BASE != STAGING_BASE:
        raise PermissionError("Unexpected staging base")
    source = inspect.getsource(combined.run)
    for name in ("broker.sock", "ledger.sqlite", "journal.sqlite",
                 "trusted.sqlite", "broker.key"):
        if name not in source:
            raise PermissionError("Missing staging fixture: " + name)
    if "BASE + \"/combined-cutover-\"" not in source:
        raise PermissionError("Combined cutover fixture not isolated")
    if "isolated-test" not in inspect.getsource(combined.RealSocketCutoverAdapter.start_new):
        raise PermissionError("Combined broker lacks isolated-test gate")
    if "isolated-test" not in inspect.getsource(replay.run):
        raise PermissionError("Replay broker lacks isolated-test gate")
    if "isolated_candidate" not in inspect.getsource(candidate.serve_candidate):
        raise PermissionError("Candidate isolation guard missing")
    if not cutover.OLD.startswith("hermes-cutover-e2e-") or not cutover.NEW.startswith("hermes-cutover-e2e-"):
        raise PermissionError("Cutover units lack isolated prefix")
    if "--broker-socket" not in inspect.getsource(operator_service.main):
        raise PermissionError("Operator broker endpoint not deployment-configured")
    # Inspect actual harness references rather than declaring runtime success.
    for module in (combined, replay):
        path = pathlib.Path(inspect.getfile(module))
        data = path.read_text(encoding="utf-8")
        for production in PRODUCTION_PATHS:
            if production in data:
                raise PermissionError("Production path in staging harness: " + production)
    print("STAGING_FIXTURE_PATH_ISOLATION=PASS")
    print("STAGING_CANDIDATE_ISOLATED_MODE=PASS")
    print("STAGING_TRANSIENT_UNIT_PREFIX=PASS")
    print("STAGING_OPERATOR_END_TO_END=NOT_TESTED")
    print("STAGING_RUNTIME_ISOLATION=NOT_ATTESTED")
    print("PRODUCTION_CUTOVER_GO=NO")


if __name__ == "__main__":
    audit()
