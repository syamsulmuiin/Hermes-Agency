"""Transport integration using a simulated peer UID.

This is NOT a real cross-UID OS acceptance test. Real Linux user separation
must be validated on the deployment host before enabling agent execution.
"""
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from agency.cross_uid_listener import serve_cross_uid_once
from agency.trusted_client import send_stage_confirmed


class CrossUidAcknowledgementTests(unittest.TestCase):
    def test_confirmed_stage_over_listener(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o710)
            path = os.path.join(folder, "trusted.sock")
            boundary = Mock()
            results = []
            failures = []
            stage = {"completed": [], "output": [], "notes": [], "blockers": []}

            def client():
                try:
                    for _ in range(200):
                        if os.path.exists(path):
                            break
                        time.sleep(0.01)
                    results.append(send_stage_confirmed(
                        path, "task", "ceo", stage, "credential"
                    ))
                except Exception as exc:
                    failures.append(exc)

            worker = threading.Thread(target=client)
            worker.start()
            try:
                with patch("agency.trusted_peer.peer_credentials",
                           return_value={"pid": 100, "uid": os.geteuid() + 1,
                                         "gid": os.getegid()}):
                    outcome = serve_cross_uid_once(
                        path, boundary, frozenset({os.geteuid() + 1}),
                        os.getegid(), acknowledged=True
                    )
            finally:
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(results, [True])
            self.assertEqual(outcome, "accepted")
            boundary.submit_stage.assert_called_once()
            self.assertFalse(os.path.lexists(path))

    def test_denied_peer_never_advances_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o710)
            path = os.path.join(folder, "trusted.sock")
            boundary = Mock()
            failures = []
            stage = {"completed": [], "output": [], "notes": [], "blockers": []}

            def client():
                try:
                    for _ in range(200):
                        if os.path.exists(path):
                            break
                        time.sleep(0.01)
                    send_stage_confirmed(path, "task", "ceo", stage, "credential")
                except Exception as exc:
                    failures.append(exc)

            worker = threading.Thread(target=client)
            worker.start()
            try:
                with patch("agency.trusted_peer.peer_credentials",
                           return_value={"pid": 100, "uid": os.geteuid() + 2,
                                         "gid": os.getegid()}):
                    outcome = serve_cross_uid_once(
                        path, boundary, frozenset({os.geteuid() + 1}),
                        os.getegid(), acknowledged=True
                    )
            finally:
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(outcome, "denied")
            self.assertEqual(len(failures), 1)
            self.assertIsInstance(failures[0], PermissionError)
            boundary.submit_stage.assert_not_called()
            self.assertFalse(os.path.lexists(path))
