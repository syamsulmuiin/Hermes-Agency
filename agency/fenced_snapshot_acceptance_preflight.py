"""Read-only, fail-closed preflight for the accepted fenced snapshot.

This module never starts a broker, installs units, provisions state, or authorizes cutover.
"""
import argparse
import os
from pathlib import Path
import stat
import subprocess
import sys

COMMIT = "9bf261261b5948bc021780548dfb5a40e68cc76f"
SNAPSHOT = Path("/opt/hermes-fenced-" + COMMIT[:12])
PRODUCTION = (
    "hermes-agency.service",
    "hermes-signed-broker.service",
    "hermes-operator-sidecar.service",
)
CANDIDATE = (
    "hermes-fenced-broker-candidate.service",
    "hermes-fenced-recovery-candidate.service",
)
MODULES = (
    "agency.real_candidate_socket_replay_e2e",
    "agency.real_candidate_pid1_recovery_e2e",
    "agency.isolated_sidecar_rehearsal",
    "agency.fenced_broker_candidate",
    "agency.operator_control",
)


def command(argv, *, cwd=None, env=None):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                          timeout=20, check=False)


def audit(repo):
    failures = []
    def fail(message):
        failures.append(message)

    if os.geteuid() != 0:
        fail("Root required to attest root-owned snapshot and host service state")
    if not SNAPSHOT.is_dir() or SNAPSHOT.is_symlink():
        fail("Expected snapshot absent or symlink")
    if not repo.is_dir() or repo.is_symlink():
        fail("Source repository absent or symlink")
    if not failures:
        revision = command(["git", "rev-parse", COMMIT + "^{commit}"], cwd=repo)
        if revision.returncode or revision.stdout.decode().strip() != COMMIT:
            fail("Pinned Git commit unavailable")
        tree = command(["git", "ls-tree", "-rz", "--full-tree", COMMIT], cwd=repo)
        if tree.returncode:
            fail("Cannot enumerate pinned Git tree")
        else:
            expected = {}
            for record in tree.stdout.split(b"\0"):
                if not record:
                    continue
                metadata, name = record.split(b"\t", 1)
                mode, kind, oid = metadata.split()
                if kind != b"blob" or mode not in (b"100644", b"100755"):
                    fail("Unsupported Git tree entry")
                    break
                expected[os.fsdecode(name)] = (mode, oid.decode("ascii"))
            actual = set()
            for directory, dirs, names in os.walk(SNAPSHOT, followlinks=False):
                for name in dirs + names:
                    path = Path(directory) / name
                    info = path.lstat()
                    if info.st_uid != 0 or stat.S_ISLNK(info.st_mode):
                        fail("Snapshot contains non-root-owned or symlink entry")
                    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                        fail("Snapshot contains unsupported file type")
                    if info.st_mode & 0o022:
                        fail("Snapshot contains group/other-writable entry")
                for name in names:
                    path = Path(directory) / name
                    relative = path.relative_to(SNAPSHOT).as_posix()
                    actual.add(relative)
                    info = path.lstat()
                    entry = expected.get(relative)
                    if entry is None or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        fail("Unexpected snapshot file: " + relative)
                        continue
                    mode, oid = entry
                    wanted = 0o755 if mode == b"100755" else 0o644
                    if stat.S_IMODE(info.st_mode) != wanted:
                        fail("Snapshot file mode mismatch: " + relative)
                    digest = command(["git", "hash-object", "--", str(path)], cwd=repo)
                    if digest.returncode or digest.stdout.decode().strip() != oid:
                        fail("Snapshot content mismatch: " + relative)
            if actual != set(expected):
                fail("Snapshot inventory differs from pinned Git tree")
            else:
                print("SNAPSHOT_FILE_COUNT=" + str(len(actual)))
    if not failures:
        script = ("import importlib,pathlib,sys; root=pathlib.Path(sys.argv[1]); "
                  "names=sys.argv[2:]; "
                  "[(lambda m: print('MODULE_ORIGIN=' + m.__name__ + '=' + str(pathlib.Path(m.__file__).resolve(strict=True))))"
                  "(importlib.import_module(n)) for n in names]")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SNAPSHOT)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        imported = command([sys.executable, "-B", "-c", script,
                            str(SNAPSHOT), *MODULES], cwd=SNAPSHOT, env=env)
        origins = {}
        if imported.returncode:
            fail("Snapshot module import failed")
        else:
            for line in imported.stdout.decode("utf-8", "replace").splitlines():
                if line.startswith("MODULE_ORIGIN="):
                    name, _, path = line[len("MODULE_ORIGIN="):].partition("=")
                    origins[name] = path
            for name in MODULES:
                wanted = str(SNAPSHOT / (name.replace(".", "/") + ".py"))
                if origins.get(name) != wanted:
                    fail("Module not loaded from snapshot: " + name)
    for service in PRODUCTION:
        result = command(["/usr/bin/systemctl", "is-active", service])
        if result.returncode or result.stdout.strip() != b"active":
            fail("Production service not active: " + service)
    for service in CANDIDATE:
        result = command(["/usr/bin/systemctl", "is-active", service])
        if result.stdout.strip() != b"inactive":
            fail("Installed candidate not inactive: " + service)
    if not Path("/run/hermes-operator/admission.freeze").exists():
        fail("Production admission freeze absent")
    for item in failures:
        print("SNAPSHOT_ACCEPTANCE_BLOCKER=" + item)
    print("SNAPSHOT_ACCEPTANCE_PREFLIGHT=" + ("PASS" if not failures else "NO_GO"))
    print("E2E_EXECUTED=NO")
    print("PRODUCTION_MUTATED=NO")
    print("PRODUCTION_CUTOVER_GO=NO")
    return 0 if not failures else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--repo", default="/root/Hermes-Agency")
    args = parser.parse_args(argv)
    return audit(Path(args.repo))


if __name__ == "__main__":
    sys.exit(main())
