import os
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from agency.trusted_service import serve_bounded


class TrustedServiceTests(unittest.TestCase):
    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            serve_bounded("/tmp/unused.sock", Mock(), frozenset({os.getuid()}), 0)

    def test_multiple_invalid_requests_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o700)
            path = directory + "/trusted.sock"
            boundary = Mock()
            results = []
            worker = threading.Thread(
                target=lambda: results.append(
                    serve_bounded(path, boundary, frozenset({os.getuid()}), 2)
                )
            )
            worker.start()
            try:
                for _ in range(200):
                    if os.path.exists(path):
                        break
                    time.sleep(0.01)
                self.assertTrue(os.path.exists(path))
                for _ in range(2):
                    with socket.socket(socket.AF_UNIX) as client:
                        client.connect(path)
                        client.sendall(b"invalid")
                        client.shutdown(socket.SHUT_WR)
            finally:
                worker.join(timeout=6)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results, [{"accepted": 0, "denied": 2}])
            boundary.submit_stage.assert_not_called()
            self.assertFalse(os.path.lexists(path))
