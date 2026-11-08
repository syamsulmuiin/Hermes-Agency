"""Read-only pinned Git tree versus root-owned staging snapshot comparison."""
import hashlib
import os
from pathlib import Path
import re
import stat

from .staging_snapshot_fd import inventory
import subprocess

_SHA = re.compile(r"[0-9a-f]{40}")


def _git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise PermissionError("Pinned Git tree unavailable")
    return result.stdout


def audit(snapshot, repo, commit, *, git=_git):
    """Compare complete Git blob inventory and snapshot; never authorize execution."""
    if not isinstance(commit, str) or not _SHA.fullmatch(commit):
        raise ValueError("A full pinned SHA-1 commit is required")
    resolved = git(repo, "rev-parse", "--verify", commit + "^{commit}").decode().strip()
    if resolved != commit:
        raise PermissionError("Git commit mismatch")
    tree = git(repo, "ls-tree", "-rz", "--full-tree", commit)
    expected = {}
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        meta, sep, raw_name = entry.partition(b"\t")
        if not sep:
            raise PermissionError("Malformed Git tree")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != b"blob" or parts[0] not in (b"100644", b"100755"):
            raise PermissionError("Unsupported Git entry")
        name = os.fsdecode(raw_name)
        if (name.startswith("/") or ".." in Path(name).parts or
                name in expected or not name):
            raise PermissionError("Unsafe Git entry")
        expected[name] = (0o755 if parts[0] == b"100755" else 0o644,
                          parts[2].decode("ascii"))
    if not expected:
        raise PermissionError("Empty pinned Git tree")
    files, directories = inventory(snapshot)
    expected_dirs = set()
    for relative in expected:
        parts = Path(relative).parts[:-1]
        for i in range(1, len(parts) + 1):
            expected_dirs.add(Path(*parts[:i]).as_posix())
    if set(files) != set(expected) or directories != expected_dirs:
        raise PermissionError("Snapshot inventory mismatch")
    for relative, (mode, data) in files.items():
        wanted_mode, oid = expected[relative]
        if mode != wanted_mode:
            raise PermissionError("Snapshot file mode mismatch")
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\\0" + data).hexdigest()
        if blob != oid:
            raise PermissionError("Snapshot file hash mismatch")
    actual = set(files)
    return {"commit": commit, "file_count": len(actual),
            "tree_content_matches": True, "production_mutated": False,
            "execute_authorized": False}
