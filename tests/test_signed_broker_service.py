import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.signed_broker_service import (provision_broker_key,
                                          read_broker_key, submit_signed_grant)


class BrokerKeyBoundaryTests(unittest.TestCase):
    def test_nonroot_cannot_provision(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("agency.signed_broker_service.os.geteuid", return_value=995):
                with self.assertRaises(PermissionError):
                    provision_broker_key(str(Path(directory) / "key"), 986)

    def test_nonroot_cannot_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            path.write_bytes(b"k"*64)
            with patch("agency.signed_broker_service.os.geteuid", return_value=995):
                with self.assertRaises(PermissionError):
                    read_broker_key(str(path), 997, 986)

    def test_reject_world_readable_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            path.write_bytes(b"k"*64)
            path.chmod(0o644)
            with patch("agency.signed_broker_service.os.geteuid", return_value=0):
                with self.assertRaises(PermissionError):
                    read_broker_key(str(path), 997, os.getgid())

    def test_reject_existing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            path.write_text("existing")
            with patch("agency.signed_broker_service.os.geteuid", return_value=0):
                with self.assertRaises((FileExistsError, PermissionError)):
                    provision_broker_key(str(path), os.getgid())
            self.assertEqual(path.read_text(), "existing")

    def test_reject_oversized_grant_before_socket(self):
        with self.assertRaises(ValueError):
            submit_signed_grant("/does/not/exist", {"payload": "x"*5000})


if __name__ == "__main__":
    unittest.main()
