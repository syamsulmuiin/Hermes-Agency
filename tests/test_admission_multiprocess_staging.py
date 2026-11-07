"""Real multi-process admission lease acceptance in disposable staging paths.

Never touches /run/hermes-admission or production services.
"""
import multiprocessing as mp
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from agency.operator_control import operator_admission_lease
from agency import production_admission_drain as drain


def _hold_shared(path, ready, release, result):
    try:
        with operator_admission_lease(path):
            ready.set()
            if not release.wait(5):
                raise TimeoutError("shared lease release timed out")
        result.put("PASS")
    except BaseException as exc:
        ready.set()
        result.put(type(exc).__name__ + ":" + str(exc))


@unittest.skipUnless(os.geteuid() == 0, "Root-owned 0640 lock fixture required")
class MultiprocessAdmissionTests(unittest.TestCase):
    def test_two_shared_holders_drain_and_reopen(self):
        with tempfile.TemporaryDirectory(prefix="hermes-admission-staging-") as tmp:
            path = os.path.join(tmp, "admission.lock")
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
            os.close(fd)
            os.chmod(path, 0o640)
            ctx = mp.get_context("spawn")
            release = ctx.Event()
            ready = [ctx.Event(), ctx.Event()]
            result = ctx.Queue()
            processes = [
                ctx.Process(target=_hold_shared, args=(path, ready[i], release, result))
                for i in range(2)
            ]
            try:
                for process in processes:
                    process.start()
                for event in ready:
                    self.assertTrue(event.wait(5), "shared lease not ready")
                self.assertTrue(all(p.is_alive() for p in processes))
                with patch.object(drain, "LOCK", path):
                    with self.assertRaises(TimeoutError):
                        with drain.exclusive_admission_drain(timeout=0.1):
                            pass
                release.set()
                for process in processes:
                    process.join(5)
                    self.assertEqual(process.exitcode, 0)
                self.assertEqual([result.get(timeout=2) for _ in processes], ["PASS", "PASS"])
                with patch.object(drain, "LOCK", path):
                    with drain.exclusive_admission_drain(timeout=1):
                        with self.assertRaises(PermissionError):
                            with operator_admission_lease(path):
                                pass
                with operator_admission_lease(path):
                    pass
            finally:
                release.set()
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                    process.join(2)


if __name__ == "__main__":
    unittest.main()
