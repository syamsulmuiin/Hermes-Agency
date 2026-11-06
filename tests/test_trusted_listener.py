import os
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from agency.trusted_listener import listen_once


class TrustedListenerTests(unittest.TestCase):
    def test_existing_path_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            path = folder + "/service.sock"
            with open(path, "w") as stream:
                stream.write("sentinel")
            with self.assertRaises(FileExistsError):
                listen_once(path, Mock(), frozenset({os.getuid()}))
            with open(path) as stream:
                self.assertEqual(stream.read(), "sentinel")

    def test_invalid_allowlist_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            with self.assertRaises(ValueError):
                listen_once(folder + "/service.sock", Mock(), frozenset())

    def test_one_connection_rejects_invalid_request(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            path = folder + "/service.sock"
            boundary = Mock()
            errors = []
            def server():
                try:
                    listen_once(path, boundary, frozenset({os.getuid()}))
                except ValueError as exc:
                    errors.append(str(exc))
            thread = threading.Thread(target=server)
            thread.start()
            try:
                for _ in range(100):
                    if os.path.exists(path):
                        break
                    time.sleep(0.01)
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(path)
                    client.sendall(b"invalid")
                    client.shutdown(socket.SHUT_WR)
            finally:
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertTrue(errors)
            boundary.submit_stage.assert_not_called()
            self.assertFalse(os.path.lexists(path))
