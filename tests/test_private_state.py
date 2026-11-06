import os
import tempfile
import unittest

from agency.private_state import verify_private_state


class PrivateStateTests(unittest.TestCase):
    def test_owner_only_state_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            keys = os.path.join(root, "keys")
            os.mkdir(keys, 0o700)
            database = os.path.join(root, "workflow.db")
            with open(database, "wb"):
                pass
            os.chmod(database, 0o600)
            self.assertTrue(verify_private_state(root, database, keys))

    def test_group_readable_db_denied(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            keys = os.path.join(root, "keys")
            os.mkdir(keys, 0o700)
            database = os.path.join(root, "workflow.db")
            with open(database, "wb"):
                pass
            os.chmod(database, 0o640)
            with self.assertRaises(PermissionError):
                verify_private_state(root, database, keys)

    def test_symlink_key_directory_denied(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            keys = os.path.join(root, "keys")
            real = os.path.join(root, "actual")
            os.mkdir(real, 0o700)
            os.symlink(real, keys)
            database = os.path.join(root, "workflow.db")
            with open(database, "wb"):
                pass
            os.chmod(database, 0o600)
            with self.assertRaises(PermissionError):
                verify_private_state(root, database, keys)

    def test_world_readable_wal_denied(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            keys = os.path.join(root, "keys")
            os.mkdir(keys, 0o700)
            database = os.path.join(root, "workflow.db")
            with open(database, "wb"):
                pass
            os.chmod(database, 0o600)
            with open(database + "-wal", "wb"):
                pass
            os.chmod(database + "-wal", 0o644)
            with self.assertRaises(PermissionError):
                verify_private_state(root, database, keys)
