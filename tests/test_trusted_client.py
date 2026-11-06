import json
import os
import socket
import tempfile
import threading
import unittest

from agency.trusted_client import send_stage


class TrustedClientTests(unittest.TestCase):
    def test_invalid_payload_never_connects(self):
        with self.assertRaises(ValueError):
            send_stage("/no/socket", "task", "ceo", {}, "credential")

    def test_request_sent_over_local_socket(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + "/trusted.sock"
            payloads = []
            ready = threading.Event()
            def receiver():
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                    listener.bind(path)
                    listener.listen(1)
                    ready.set()
                    conn, _ = listener.accept()
                    with conn:
                        pieces = []
                        while True:
                            part = conn.recv(4096)
                            if not part:
                                break
                            pieces.append(part)
                        payloads.append(json.loads(b"".join(pieces)))
            thread = threading.Thread(target=receiver)
            thread.start()
            try:
                self.assertTrue(ready.wait(3))
                result = {"completed": [], "output": [], "notes": [], "blockers": []}
                self.assertIsNone(send_stage(path, "task", "ceo", result, "credential"))
            finally:
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(payloads[0]["agent"], "ceo")
            self.assertEqual(payloads[0]["result"], result)

    def test_timeout_bounds(self):
        with self.assertRaises(ValueError):
            send_stage("/no/socket", "task", "ceo", {}, "credential", timeout=0)
