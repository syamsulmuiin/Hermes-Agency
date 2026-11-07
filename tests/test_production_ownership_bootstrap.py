"""Fail-closed checks for production bootstrap preconditions."""
import unittest
from unittest.mock import patch
from agency import production_ownership_bootstrap as module


class BootstrapSafetyTests(unittest.TestCase):
    def test_requires_root(self):
        with patch.object(module.os, "geteuid", return_value=1000):
            with self.assertRaises(PermissionError):
                module.bootstrap()

    def test_requires_freeze_marker(self):
        with patch.object(module.os, "geteuid", return_value=0):
            with patch.object(module.os, "lstat", side_effect=FileNotFoundError):
                with self.assertRaises(FileNotFoundError):
                    module.bootstrap()

    def test_unknown_systemd_state_fails_closed(self):
        class Result:
            returncode = 1
            stdout = b"unknown\n"
        with patch.object(module.subprocess, "run", return_value=Result()):
            self.assertFalse(module._inactive("hermes-signed-broker.service"))


if __name__ == "__main__":
    unittest.main()
