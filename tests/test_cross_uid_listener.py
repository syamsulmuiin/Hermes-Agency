import os
import tempfile
import unittest
from unittest.mock import Mock

from agency.cross_uid_listener import serve_cross_uid_once


class CrossUidListenerTests(unittest.TestCase):
    def test_server_uid_cannot_be_client(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o710)
            with self.assertRaises(ValueError):
                serve_cross_uid_once(
                    directory + "/trusted.sock", Mock(),
                    frozenset({os.geteuid()}), os.getegid()
                )

    def test_wrong_group_denied_before_bind(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o710)
            path = directory + "/trusted.sock"
            with self.assertRaises(PermissionError):
                serve_cross_uid_once(
                    path, Mock(), frozenset({os.geteuid() + 1}),
                    os.getegid() + 1
                )
            self.assertFalse(os.path.lexists(path))

    def test_existing_path_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o710)
            path = directory + "/trusted.sock"
            with open(path, "w") as stream:
                stream.write("sentinel")
            with self.assertRaises(PermissionError):
                serve_cross_uid_once(
                    path, Mock(), frozenset({os.geteuid() + 1}),
                    os.getegid()
                )
            with open(path) as stream:
                self.assertEqual(stream.read(), "sentinel")
