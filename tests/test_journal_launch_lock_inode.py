"""Fail closed if a privileged actor replaces the journal launch lock pathname."""
import os
import pathlib
import tempfile
import unittest

from agency.fenced_staging_serialization import staging_journal_lock
from agency.fenced_unit_journal import _connect


@unittest.skipUnless(os.geteuid() == 0, "Root-only journal lock")
class JournalLockInodeTests(unittest.TestCase):
    def test_replacement_while_held_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="hermes-launch-inode-") as directory:
            journal = pathlib.Path(directory) / "owned-units.sqlite"
            with _connect(str(journal)):
                pass
            lock = pathlib.Path(str(journal) + ".launch.lock")
            with self.assertRaisesRegex(PermissionError, "inode changed"):
                with staging_journal_lock(str(journal)):
                    lock.unlink()
                    lock.touch(mode=0o600)
            self.assertTrue(lock.exists())

    def test_unmodified_lock_is_accepted(self):
        with tempfile.TemporaryDirectory(prefix="hermes-launch-inode-") as directory:
            journal = pathlib.Path(directory) / "owned-units.sqlite"
            with _connect(str(journal)):
                pass
            with staging_journal_lock(str(journal)):
                self.assertTrue(pathlib.Path(str(journal) + ".launch.lock").is_file())


if __name__ == "__main__":
    unittest.main()
