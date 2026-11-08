"""Non-authorizing production readiness evidence synthesis.

Read-only runtime and installed recovery checks are performed now. Historical
staging results are reported as operator-supplied observations, never as fresh
production attestations. No socket requests or lock acquisition.
"""
import argparse
import datetime
import json
import sys

from .production_runtime_evidence import capture
from .production_recovery_wiring_evidence import inspect
from .production_six_blocker_acceptance import BLOCKERS


def collect(runtime_probe=capture, recovery_probe=inspect):
    observations = {}
    for name, probe in (("runtime_identity", runtime_probe),
                        ("recovery_wiring", recovery_probe)):
        try:
            value = probe()
            if value.get("cutover_authorized") is not False:
                raise PermissionError("Probe attempted to authorize cutover")
            observations[name] = {"status": "PASS", "evidence": value}
        except (OSError, ValueError, PermissionError, KeyError) as exc:
            observations[name] = {"status": "UNVERIFIED",
                                  "error": type(exc).__name__}
    return {
        "schema": "hermes-production-readiness-synthesis-v1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "production_cutover_go": False,
        "decision": "NO_GO",
        "production_mutated_by_audit": False,
        "fresh_read_only": observations,
        "previously_reported": {
            "isolated_admission_behavioral": "PASS_REPORTED_NOT_REEXECUTED",
            "staging_operator_handler_e2e": "PASS_REPORTED_NOT_REEXECUTED",
            "live_socket_rejection": "PASS_REPORTED_NOT_REEXECUTED",
            "passive_kernel_observation": "INCONCLUSIVE_REPORTED_NOT_REEXECUTED",
        },
        "production_blockers": {
            name: "NOT_ATTESTED" for name in BLOCKERS
        },
        "interpretation": (
            "Staging acceptance and read-only configuration checks do not "
            "establish live production behavior. A missing ownership journal "
            "is not permission to provision one."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)
    print(json.dumps(collect(), indent=2, sort_keys=True))
    print("PRODUCTION_READINESS=NO_GO")
    return 2


if __name__ == "__main__":
    sys.exit(main())
