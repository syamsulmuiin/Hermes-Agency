"""Root-owned admission lock provisioning regression tests."""
import os
import tempfile
import unittest
from unittest.mock import patch
from agency.production_admission_provision import provision


@unittest.skipUnless(os.geteuid() == 0, "Root ownership required")
class AdmissionProvisionTests(unittest.TestCase):
    def test_idempotent_preserves_inode(self):
        with tempfile.TemporaryDirectory() as base:
            directory = os.path.join(base, "admission")
            with patch("agency.production_admission_provision.grp.getgrnam") as group:
                group.return_value.gr_gid = os.getegid()
                provision(directory)
                first = os.stat(os.path.join(directory, "admission.lock"))
                provision(directory)
                second = os.stat(os.path.join(directory, "admission.lock"))
            self.assertEqual(first.st_ino, second.st_ino)
            self.assertEqual(first.st_mode & 0o777, 0o640)

    def test_refuses_existing_untrusted_lock(self):
        with tempfile.TemporaryDirectory() as base:
            directory = os.path.join(base, "admission")
            os.mkdir(directory, 0o755)
            lock = os.path.join(directory, "admission.lock")
            with open(lock, "wb"):
                pass
            os.chmod(lock, 0o666)
            with patch("agency.production_admission_provision.grp.getgrnam") as group:
                group.return_value.gr_gid = os.getegid()
                with self.assertRaises(PermissionError):
                    provision(directory)
            self.assertEqual(os.stat(lock).st_mode & 0o777, 0o666)


if __name__ == "__main__":
    unittest.main()
