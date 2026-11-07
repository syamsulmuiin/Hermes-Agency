"""Isolated process supervisor tests; no systemd or production services."""
import socket
import sys
import threading
import time
import unittest

from agency.fence_process_supervisor import run_fence_supervised_subprocess


class FenceProcessSupervisorTests(unittest.TestCase):
    def test_short_job_succeeds_with_live_fence(self):
        a, b = socket.socketpair()
        try:
            with a, b:
                result = run_fence_supervised_subprocess(
                    (sys.executable, "-c", "pass"), a, timeout=3)
                self.assertEqual(result["exit_code"], 0)
        finally:
            pass

    def test_disconnect_denies_long_running_job(self):
        a, b = socket.socketpair()
        closer = threading.Thread(target=lambda: (time.sleep(0.15), b.close()))
        closer.start()
        try:
            with a:
                start = time.monotonic()
                with self.assertRaisesRegex(PermissionError, "disconnected"):
                    run_fence_supervised_subprocess(
                        (sys.executable, "-c", "import time; time.sleep(5)"),
                        a, timeout=3)
                self.assertLess(time.monotonic() - start, 2)
        finally:
            closer.join(timeout=2)

    def test_timeout_kills_long_running_job(self):
        a, b = socket.socketpair()
        with a, b:
            with self.assertRaisesRegex(PermissionError, "timeout"):
                run_fence_supervised_subprocess(
                    (sys.executable, "-c", "import time; time.sleep(5)"),
                    a, timeout=0.15)

    def test_unexpected_fence_traffic_denied(self):
        a, b = socket.socketpair()
        with a, b:
            b.sendall(b"unexpected")
            with self.assertRaisesRegex(PermissionError, "traffic"):
                run_fence_supervised_subprocess(
                    (sys.executable, "-c", "import time; time.sleep(5)"),
                    a, timeout=3)


if __name__ == "__main__":
    unittest.main()
