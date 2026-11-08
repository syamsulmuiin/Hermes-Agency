"""Portable deployment planning and trust-boundary checks. Never executes a plan."""
import argparse
import json
import sys

from .deployment_manifest import load, resolve, validate


def plan(manifest, resolver=resolve):
    """Return a non-executable deployment assessment for a compatible host."""
    validate(manifest)
    runtime = resolver(manifest)
    if (runtime.get("identity_resolved") is not True
            or runtime.get("runtime_behavior_attested") is not False
            or runtime.get("sandbox_authorized") is not False
            or runtime.get("cutover_authorized") is not False):
        raise PermissionError("Resolver must remain non-authorizing")
    if runtime.get("paths") != manifest["paths"] or runtime.get("units") != manifest["units"]:
        raise PermissionError("Resolver changed deployment identity")
    if set(runtime.get("uids", {})) != {"trusted_user", "worker_user"}:
        raise PermissionError("Unresolved user identities")
    if set(runtime.get("gids", {})) != {"trusted_group"}:
        raise PermissionError("Unresolved group identity")
    if (not all(type(v) is int and v > 0 for v in runtime["uids"].values())
            or not all(type(v) is int and v > 0 for v in runtime["gids"].values())):
        raise PermissionError("Invalid resolved identities")
    return {
        "schema": "hermes-portable-deployment-plan-v1",
        "mode": "READ_ONLY_PLAN",
        "paths": dict(runtime["paths"]),
        "units": dict(runtime["units"]),
        "uids": dict(runtime["uids"]),
        "gids": dict(runtime["gids"]),
        "systemctl": runtime["systemctl"],
        "installation_performed": False,
        "production_mutated": False,
        "broker_execution_authorized": False,
        "admission_authorized": False,
        "recovery_behavior_attested": False,
        "cutover_authorized": False,
        "production_readiness": "NO_GO",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only portable deployment planning")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        result = plan(load(args.manifest))
    except (OSError, ValueError, KeyError, TypeError, PermissionError) as exc:
        print("PORTABLE_DEPLOYMENT_PLAN=NO_GO")
        print("PLAN_ERROR=" + type(exc).__name__)
        print("PRODUCTION_MUTATED=NO")
        return 2
    print(json.dumps(result, sort_keys=True))
    print("PORTABLE_DEPLOYMENT_PLAN=NON_AUTHORIZING")
    print("PRODUCTION_MUTATED=NO")
    return 2


if __name__ == "__main__":
    sys.exit(main())
