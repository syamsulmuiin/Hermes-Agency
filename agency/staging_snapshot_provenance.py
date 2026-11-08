"""Read-only pinned Git tree versus root-owned staging snapshot comparison."""
import hashlib
import os
from pathlib import Path
import re
import stat
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
    root = Path(snapshot)
    root_stat = root.lstat()
    if (not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != 0
            or root_stat.st_mode & 0o022):
        raise PermissionError("Untrusted snapshot root")
    actual = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            info = path.lstat()
            if (info.st_uid != 0 or info.st_mode & 0o022
                    or stat.S_ISLNK(info.st_mode)):
                raise PermissionError("Untrusted snapshot entry")
            if name in dirs:
                if not stat.S_ISDIR(info.st_mode):
                    raise PermissionError("Invalid directory")
                continue
            relative = path.relative_to(root).as_posix()
            if relative not in expected or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PermissionError("Unexpected snapshot file")
            mode, oid = expected[relative]
            if stat.S_IMODE(info.st_mode) != mode:
                raise PermissionError("Snapshot file mode mismatch")
            with path.open("rb") as stream:
                data = stream.read()
                pinned = os.fstat(stream.fileno())
                if (pinned.st_dev, pinned.st_ino) != (info.st_dev, info.st_ino):
                    raise PermissionError("Snapshot file changed")
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if blob != oid:
                raise PermissionError("Snapshot file hash mismatch")
            actual.add(relative)
    if actual != set(expected):
        raise PermissionError("Snapshot inventory mismatch")
    return {"commit": commit, "file_count": len(actual),
            "tree_content_matches": True, "production_mutated": False,
            "execute_authorized": False}
