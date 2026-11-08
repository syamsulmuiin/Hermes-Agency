"""Staging-only unit preparation. No host systemd or production mutations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from .deployment_manifest import validate as validate_manifest
from .portable_deployment_plan import plan as deployment_plan


def _regular_tree(snapshot):
    root = Path(snapshot)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise PermissionError("Snapshot root not trusted")
    hashes = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(directory) / name
            meta = p.lstat()
            if meta.st_uid != 0 or meta.st_mode & 0o022 or stat.S_ISLNK(meta.st_mode):
                raise PermissionError("Untrusted snapshot entry")
            if p.is_dir():
                if not stat.S_ISDIR(meta.st_mode):
                    raise PermissionError("Unsupported snapshot directory")
            elif not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise PermissionError("Unsupported snapshot file")
            else:
                hashes[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def validate(manifest, *, resolver, snapshot_audit=_regular_tree):
    """Verify staging inputs; no identity or snapshot result authorizes execution."""
    validate_manifest(manifest)
    report = deployment_plan(manifest, resolver=resolver)
    snapshot_hashes = snapshot_audit(manifest["paths"]["snapshot"])
    if not isinstance(snapshot_hashes, dict) or not snapshot_hashes:
        raise PermissionError("Empty or unverified snapshot inventory")
    if not all(isinstance(k, str) and isinstance(v, str) and len(v) == 64
               and all(ch in "0123456789abcdef" for ch in v)
               for k, v in snapshot_hashes.items()):
        raise PermissionError("Invalid snapshot digest inventory")
    return {"schema": "hermes-staging-validation-v1", "plan": report,
            "snapshot_files": len(snapshot_hashes),
            "snapshot_inventory_sha256": hashlib.sha256(
                json.dumps(snapshot_hashes, sort_keys=True).encode()).hexdigest(),
            "source_commit_attested": False,
            "runtime_identity_attested": False,
            "isolated_pid1_attested": False,
            "startup_gate_attested": False,
            "recovery_attested": False,
            "execute_authorized": False,
            "production_mutated": False}


def render_units(manifest, *, python="/usr/bin/python3"):
    """Prepare inert unit text; never install or activate on the host."""
    validate_manifest(manifest)
    if not python.startswith("/") or any(c in python for c in "\n\r\t "):
        raise ValueError("Unsafe interpreter")
    paths = manifest["paths"]
    units = manifest["units"]
    # No production broker or live admission paths are used in these templates.
    return {
        "broker": (
            "[Unit]\nDescription=Hermes isolated staging broker (INERT)\n"
            "Requires=" + units["candidate_recovery"] + "\n"
            "After=" + units["candidate_recovery"] + "\n"
            "OnFailure=" + units["candidate_recovery"] + "\n"
            "[Service]\nType=oneshot\nUser=root\nGroup=root\n"
            "WorkingDirectory=" + paths["snapshot"] + "\n"
            "ExecStart=" + python + " -B -m agency.portable_deployment_plan --help\n"
            "RefuseManualStart=yes\nRefuseManualStop=yes\n"
            "NoNewPrivileges=yes\nProtectSystem=strict\nProtectHome=yes\n"
        ),
        "recovery": (
            "[Unit]\nDescription=Hermes isolated staging recovery (INERT)\n"
            "[Service]\nType=oneshot\nUser=root\nGroup=root\n"
            "WorkingDirectory=" + paths["snapshot"] + "\n"
            "ExecStart=" + python + " -B -m agency.portable_deployment_plan --help\n"
            "RefuseManualStart=yes\nRefuseManualStop=yes\n"
            "NoNewPrivileges=yes\nProtectSystem=strict\nProtectHome=yes\n"
        ),
    }


def execute(*, isolation_attestation=None):
    """Never execute on a shared host. Isolated PID1 runner not implemented."""
    raise PermissionError("Staging execution disabled until independent isolation attestation and runner exist")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Non-executing staging installer preparation")
    parser.add_argument("mode", choices=("plan", "validate", "execute"))
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    if args.mode == "execute":
        print("STAGING_EXECUTION=DENIED")
        print("PRODUCTION_MUTATED=NO")
        return 2
    from .deployment_manifest import load, resolve
    try:
        manifest = load(args.manifest)
        if args.mode == "plan":
            result = deployment_plan(manifest)
        else:
            result = validate(manifest, resolver=resolve)
    except (OSError, ValueError, KeyError, TypeError, PermissionError) as exc:
        print("STAGING_" + args.mode.upper() + "=NO_GO")
        print("ERROR=" + type(exc).__name__)
        print("PRODUCTION_MUTATED=NO")
        return 2
    print(json.dumps(result, sort_keys=True))
    print("STAGING_" + args.mode.upper() + "=NON_AUTHORIZING")
    print("PRODUCTION_MUTATED=NO")
    return 2


if __name__ == "__main__":
    sys.exit(main())
