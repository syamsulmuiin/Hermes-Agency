"""Isolated admission behavior: distinguish flock denial from freeze denial.

Never uses /run/hermes-admission, the production operator socket, or a
production credential. Does not authorize production cutover.
"""
import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from agency.operator_control import dispatch_operator, operator_admission_lease


@unittest.skipUnless(os.geteuid() == 0, "root-owned 0640 lock required")
class IsolatedAdmissionBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hermes-admission-isolated-")
        self.addCleanup(self.tmp.cleanup)
        self.lock = str(Path(self.tmp.name) / "admission.lock")
        fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
        os.close(fd)
        os.chmod(self.lock, 0o640)
        self.freeze = str(Path(self.tmp.name) / "admission.freeze")
        self.boundary = Mock()
        self.request = {"action": "approve", "approval_id": "isolated",
                        "operator_secret_hex": "00" * 32}
        self.verifier = ("isolated", b"0" * 16, b"0" * 32)

    def dispatch(self):
        return dispatch_operator(self.boundary, self.request, self.verifier,
                                 "/isolated/no-broker-key", "/isolated/no-broker-socket",
                                 admission_lock=self.lock, freeze_marker=self.freeze)

    def test_freeze_denies_with_uncontended_lock(self):
        Path(self.freeze).touch()
        with self.assertRaisesRegex(PermissionError, "frozen"):
            self.dispatch()
        self.boundary.approve_operator_request.assert_not_called()

    def test_exclusive_lock_denies_without_freeze(self):
        # A distinct open-file description is required to model another process.
        fd = os.open(self.lock, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(PermissionError, "locked for maintenance"):
                self.dispatch()
            self.boundary.approve_operator_request.assert_not_called()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_unfrozen_uncontended_lock_reaches_approval_only(self):
        self.dispatch()
        self.boundary.approve_operator_request.assert_called_once()
        self.boundary.execute_operator_approved_job.assert_not_called()

    def test_inode_replacement_denied(self):
        with self.assertRaisesRegex(PermissionError, "inode changed"):
            with operator_admission_lease(self.lock):
                os.unlink(self.lock)
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
                os.close(fd)
                os.chmod(self.lock, 0o640)


if __name__ == "__main__":
    unittest.main()
