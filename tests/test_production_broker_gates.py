import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agency.broker_key_rotation import rotate_broker_key
from agency.supervised_broker import serve_forever


class ProductionIntegrationGates(unittest.TestCase):
    def test_rotation_rejects_nonroot(self):
        with patch("agency.broker_key_rotation.os.geteuid", return_value=995):
            with self.assertRaises(PermissionError):
                rotate_broker_key("/tmp/nonexistent", 997, 986)

    def test_supervisor_rejects_nonroot(self):
        with patch("agency.supervised_broker.os.geteuid", return_value=995):
            with self.assertRaises(PermissionError):
                serve_forever("/tmp/no", 997, 986, "/tmp/ledger",
                              "/tmp/trusted", "/tmp/key")

    def test_rotation_requires_verified_existing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "missing")
            with patch("agency.broker_key_rotation.os.geteuid", return_value=0):
                with self.assertRaises((PermissionError, FileNotFoundError)):
                    rotate_broker_key(path, 997, 986)
            self.assertFalse(os.path.exists(path + ".new"))


if __name__ == "__main__":
    unittest.main()
