"""Fail-closed tests for read-only production runtime evidence."""
import stat
import subprocess
import unittest
from unittest.mock import Mock, patch

from agency import production_runtime_evidence as evidence


class RuntimeEvidenceTests(unittest.TestCase):
    def state(self):
        return {"ActiveState": "active", "MainPID": "1234",
                "WorkingDirectory": str(evidence.SNAPSHOT),
                "Environment": "PYTHONPATH=" + str(evidence.SNAPSHOT),
                "User": "hermes-trusted", "Group": "hermes-trusted"}

    def capture(self, changes=None, *, freeze=True, inode=88):
        state = self.state()
        state.update(changes or {})
        lock = Mock(st_mode=stat.S_IFREG | 0o640, st_uid=0,
                    st_nlink=1, st_dev=25, st_ino=inode)
        with patch.object(evidence, "_show", return_value=state), \
             patch.object(evidence.SNAPSHOT.__class__, "is_symlink", return_value=False), \
             patch.object(evidence.SNAPSHOT.__class__, "is_dir", return_value=True), \
             patch.object(evidence.SNAPSHOT.__class__, "exists", return_value=freeze), \
             patch.object(evidence.os, "readlink", return_value=str(evidence.SNAPSHOT)), \
             patch.object(evidence.Path, "read_bytes",
                          return_value=b"/usr/bin/python3\\0-m\\0agency.operator_service\\0"), \
             patch.object(evidence.Path, "lstat", return_value=lock):
            return evidence.capture()

    def test_success_is_not_cutover_authorization(self):
        report = self.capture()
        self.assertEqual(report["runtime_identity"], "PASS")
        self.assertFalse(report["cutover_authorized"])
        self.assertEqual(report["admission_behavior"], "NOT_ATTESTED")

    def test_rejects_stale_pid(self):
        with self.assertRaises(PermissionError):
            self.capture({"MainPID": "0"})

    def test_rejects_wrong_snapshot(self):
        with self.assertRaises(PermissionError):
            self.capture({"WorkingDirectory": "/opt/untrusted"})

    def test_rejects_wrong_identity(self):
        with self.assertRaises(PermissionError):
            self.capture({"User": "root"})

    def test_rejects_missing_freeze(self):
        with self.assertRaises(PermissionError):
            self.capture(freeze=False)

    def test_cli_never_returns_go(self):
        with patch.object(evidence, "capture", return_value={"cutover_authorized": False}):
            self.assertEqual(evidence.main(["--read-only"]), 2)

    def test_cli_fails_closed_on_systemd_error(self):
        with patch.object(evidence, "capture",
                          side_effect=subprocess.CalledProcessError(1, "systemctl")):
            self.assertEqual(evidence.main(["--read-only"]), 2)


if __name__ == "__main__":
    unittest.main()
