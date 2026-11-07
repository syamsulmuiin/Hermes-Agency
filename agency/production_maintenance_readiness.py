"""Read-only readiness evidence evaluator for isolated acceptance.

This evaluates an independently collected evidence mapping. It never gathers
or fabricates live proof and never authorizes a production cutover.
"""
from dataclasses import dataclass

REQUIRED = (
    "pinned_runtime_identity",
    "live_admission_participation",
    "exclusive_drain_inode_stability",
    "durable_freeze_and_quiescence",
    "journal_recovery_and_replay_persistence",
    "verified_service_handover",
    "verified_route_and_replay_rejection",
    "verified_rollback",
    "durable_quarantine_on_rollback_failure",
    "empty_run_boot_provisioning",
    "independent_pid1_recovery",
    "authorized_maintenance_window",
)


@dataclass(frozen=True)
class ReadinessResult:
    status: str
    blockers: tuple


def evaluate(evidence, *, production_attested=False):
    """Evidence completeness only; even complete evidence is not cutover approval."""
    blockers = []
    if not isinstance(evidence, dict):
        evidence = {}
    for name in REQUIRED:
        if evidence.get(name) is not True:
            blockers.append(name)
    if production_attested is not True:
        blockers.append("independent_live_production_attestation_missing")
    return ReadinessResult("EVIDENCE_COMPLETE_NOT_AUTHORIZED" if not blockers else "NO_GO", tuple(blockers))


def main():
    # Deliberately no --execute, --go, or evidence-file auto-authorization.
    result = evaluate({})
    print("PRODUCTION_READINESS=" + result.status)
    for blocker in result.blockers:
        print("PRODUCTION_BLOCKER=" + blocker)
    print("PRODUCTION_MUTATED=NO")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
