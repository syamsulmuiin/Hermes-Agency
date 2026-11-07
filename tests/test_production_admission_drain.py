"""Admission lock contention and drain regression tests."""
import os
import tempfile
import unittest
from unittest.mock import patch

from agency.operator_control import operator_admission_lease
from agency import production_admission_drain as drain


class AdmissionDrainTests(unittest.TestCase):
    def test_exclusive_drain_blocks_new_shared_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "admission.lock")
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
