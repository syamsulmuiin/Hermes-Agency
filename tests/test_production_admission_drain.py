"""Admission lock contention and drain regression tests."""
import os
import tempfile
import unittest
from unittest.mock import patch

from agency.operator_control import operator_admission_lease
from agency import production_admission_drain as drain


@unittest.skipUnless(os.geteuid() == 0, "Root-owned lock fixture required")
class AdmissionDrainTests(unittest.TestCase):
    def test_replaced_inode_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "admission.lock")
            with open(path, "wb"):
                pass
            os.chmod(path, 0o640)
            with operator_admission_lease(path):
                pass
            original = os.stat(path)
            replacement = os.path.join(directory, "replacement")
            with open(replacement, "wb"):
                pass
            with patch("agency.operator_control.os.stat", return_value=os.stat(replacement)):
                with self.assertRaisesRegex(PermissionError, "inode changed"):
                    with operator_admission_lease(path):
                        pass
            self.assertEqual(os.stat(path).st_ino, original.st_ino)

    def test_missing_and_unsafe_lock_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "admission.lock")
            with self.assertRaises(FileNotFoundError):
                with operator_admission_lease(path):
                    pass
            with open(path, "wb"):
                pass
            os.chmod(path, 0o666)
            with self.assertRaisesRegex(PermissionError, "Unsafe admission lock"):
                with operator_admission_lease(path):
                    pass

    def test_inode_replacement_during_admission_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "admission.lock")
            replacement = os.path.join(directory, "replacement")
            with open(path, "wb"):
                pass
            os.chmod(path, 0o640)
            with self.assertRaisesRegex(PermissionError, "inode changed during"):
                with operator_admission_lease(path):
                    os.rename(path, replacement)
                    with open(path, "wb"):
                        pass
                    os.chmod(path, 0o640)

    def test_exclusive_drain_blocks_new_shared_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "admission.lock")
            with open(path, "wb"):
                pass
            os.chmod(path, 0o640)
            with operator_admission_lease(path):
                with patch.object(drain, "LOCK", path), patch.object(
                        drain.os, "geteuid", return_value=0):
                    with self.assertRaises(TimeoutError):
                        with drain.exclusive_admission_drain(timeout=0.05):
                            pass
            with patch.object(drain, "LOCK", path), patch.object(
                    drain.os, "geteuid", return_value=0):
                with drain.exclusive_admission_drain(timeout=0.05):
                    with self.assertRaisesRegex(PermissionError, "locked"):
                        with operator_admission_lease(path):
                            pass
            with operator_admission_lease(path):
                pass


if __name__ == "__main__":
    unittest.main()
