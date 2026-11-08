"""Descriptor-relative snapshot traversal tests (root-owned test workspace)."""
import os
from pathlib import Path
import tempfile
import unittest

from agency.staging_snapshot_fd import inventory


class SnapshotFDTests(unittest.TestCase):
    def test_regular_tree_and_nested_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "agency").mkdir()
            (root / "agency" / "mod.py").write_bytes(b"ok")
            if root.stat().st_uid != 0:
                with self.assertRaises(PermissionError):
                    inventory(root)
                return
            files, directories = inventory(root)
            self.assertEqual(files["agency/mod.py"][1], b"ok")
            self.assertEqual(directories, {"agency"})

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "link").symlink_to("/etc/passwd")
            with self.assertRaises((PermissionError, OSError)):
                inventory(root)

    def test_group_writable_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "file"
            file.write_bytes(b"ok")
            file.chmod(0o664)
            with self.assertRaises(PermissionError):
                inventory(root)


if __name__ == "__main__":
    unittest.main()
