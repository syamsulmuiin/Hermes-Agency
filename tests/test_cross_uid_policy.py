import os
import socket
import tempfile
import unittest

from agency.cross_uid_policy import verify_cross_uid_transport


class CrossUidPolicyTests(unittest.TestCase):
    def test_rejects_private_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            path = folder + "/trusted.sock"
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(path)
                with self.assertRaises(PermissionError):
                    verify_cross_uid_transport(folder, path, os.getuid(), os.getgid())

    def test_rejects_wrong_group(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o710)
            path = folder + "/trusted.sock"
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(path)
                with self.assertRaises(PermissionError):
                    verify_cross_uid_transport(folder, path, os.getuid(), os.getgid() + 1)

    def test_rejects_non_socket(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o710)
            path = folder + "/trusted.sock"
            with open(path, "w") as stream:
                stream.write("not a socket")
            with self.assertRaises(PermissionError):
                verify_cross_uid_transport(folder, path, os.getuid(), os.getgid())
