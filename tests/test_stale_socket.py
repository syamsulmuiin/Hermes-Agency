"""Regression tests for conservative stale socket recovery."""
import os
import socket
import tempfile
import unittest
from unittest.mock import patch
from agency.stale_socket import recover_stale_socket


class StaleSocketTests(unittest.TestCase):
    def test_absent_path(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(recover_stale_socket(root + "/missing.sock"))

    def test_regular_file_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path = root + "/trusted.sock"
            with open(path, "w") as handle:
                handle.write("sentinel")
            with self.assertRaises(PermissionError):
                recover_stale_socket(path)
            self.assertTrue(os.path.isfile(path))

    def test_symlink_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            target = root + "/target"
            path = root + "/trusted.sock"
            with open(target, "w"):
                pass
            os.symlink(target, path)
            with self.assertRaises(PermissionError):
                recover_stale_socket(path)
            self.assertTrue(os.path.islink(path))

    def test_active_socket_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path = root + "/trusted.sock"
            listener = socket.socket(socket.AF_UNIX)
            try:
                listener.bind(path)
                listener.listen(1)
                with self.assertRaises(PermissionError):
                    recover_stale_socket(path)
                self.assertTrue(os.path.exists(path))
            finally:
                listener.close()

    def test_stale_socket_removed(self):
        with tempfile.TemporaryDirectory() as root:
            path = root + "/trusted.sock"
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(path)
            listener.listen(1)
            listener.close()
            self.assertTrue(recover_stale_socket(path))
            self.assertFalse(os.path.lexists(path))

    def test_wrong_owner_denied(self):
        with tempfile.TemporaryDirectory() as root:
            path = root + "/trusted.sock"
            listener = socket.socket(socket.AF_UNIX)
            try:
                listener.bind(path)
            finally:
                listener.close()
            with patch("agency.stale_socket.os.geteuid", return_value=os.geteuid() + 1):
                with self.assertRaises(PermissionError):
                    recover_stale_socket(path)
            self.assertTrue(os.path.lexists(path))


if __name__ == "__main__":
    unittest.main()
