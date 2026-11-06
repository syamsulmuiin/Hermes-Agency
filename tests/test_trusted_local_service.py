import os
import socket
import tempfile
import unittest
from unittest.mock import Mock

from agency.trusted_local_service import serve_one, verify_private_socket_directory


class TrustedLocalServiceTests(unittest.TestCase):
    def test_private_directory(self):
        with tempfile.TemporaryDirectory() as path:
            os.chmod(path, 0o700)
            self.assertTrue(verify_private_socket_directory(path))
            os.chmod(path, 0o755)
            with self.assertRaises(PermissionError):
                verify_private_socket_directory(path)

    def test_symlink_directory_denied(self):
        with tempfile.TemporaryDirectory() as path:
            os.chmod(path, 0o700)
            link = path + "-link"
            os.symlink(path, link)
            try:
                with self.assertRaises(PermissionError):
                    verify_private_socket_directory(link)
            finally:
                os.unlink(link)

    def test_invalid_payload_never_reaches_boundary(self):
        left, right = socket.socketpair()
        try:
            boundary = Mock()
            right.sendall(b"invalid")
            right.shutdown(socket.SHUT_WR)
            with self.assertRaises(ValueError):
                serve_one(left, boundary)
            boundary.submit_stage.assert_not_called()
        finally:
            left.close()
            right.close()
