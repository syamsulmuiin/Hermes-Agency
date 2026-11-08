"""Provenance and isolation security regression tests."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from agency.staging_snapshot_provenance import audit
from agency.staging_isolation_evidence import inspect


class ProvenanceTests(unittest.TestCase):
    def test_valid_pinned_tree_and_tamper(self):
        data = b"trusted content\n"
        oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        commit = "a" * 40
        def git(repo, *args):
            if args[0] == "rev-parse":
                return commit.encode() + b"\n"
            return b"100644 blob " + oid.encode() + b"\tfile.txt\0"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            file = path / "file.txt"
            file.write_bytes(data)
            if path.stat().st_uid == 0:
                self.assertTrue(audit(path, path, commit, git=git)["tree_content_matches"])
                file.write_bytes(b"tampered")
                with self.assertRaises(PermissionError):
                    audit(path, path, commit, git=git)
            else:
                with self.assertRaises(PermissionError):
                    audit(path, path, commit, git=git)

    def test_invalid_commit_denied(self):
        with self.assertRaises(ValueError):
            audit("/none", "/none", "main")

    def test_symlink_snapshot_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "target").mkdir()
            (root / "link").symlink_to(root / "target")
            commit = "b" * 40
            def git(repo, *args):
                if args[0] == "rev-parse":
                    return (commit + "\n").encode()
                return b"100644 blob " + b"0" * 40 + b"\tx\0"
            with self.assertRaises(PermissionError):
                audit(root / "link", root, commit, git=git)


class IsolationTests(unittest.TestCase):
    def test_shared_pid1_never_authorizes(self):
        result = inspect(readlink=lambda p: "pid:[1]",
                         read_text=lambda p: "systemd\n")
        self.assertFalse(result["isolation_attested"])
        self.assertFalse(result["execute_authorized"])
        self.assertFalse(result["filesystem_separation_attested"])


if __name__ == "__main__":
    unittest.main()
