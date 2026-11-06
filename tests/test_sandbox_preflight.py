"""Regression tests: discovery must never authorize agent execution."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.sandbox_preflight import assess_linux_isolation, require_verified_isolation


class SandboxPreflightTests(unittest.TestCase):
    def test_missing_kernel_features_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            result = assess_linux_isolation(root, root)
            self.assertFalse(result["ready"])
            self.assertFalse(result["kernel_prerequisites_present"])
            with self.assertRaises(PermissionError):
                require_verified_isolation(result)

    def test_simulated_kernel_features_do_not_enable_execution(self):
        with tempfile.TemporaryDirectory() as root:
            proc = Path(root) / "proc"
            sysroot = Path(root) / "sys"
            ns = proc / "self" / "ns"
            ns.mkdir(parents=True)
            for name in ("user", "mnt", "pid", "net", "ipc", "uts"):
                (ns / name).touch()
            (sysroot / "user").mkdir(parents=True)
            (sysroot / "user" / "max_user_namespaces").write_text("100\n")
            with patch("agency.sandbox_preflight.sys.platform", "linux"):
                result = assess_linux_isolation(str(proc), str(sysroot))
            self.assertTrue(result["kernel_prerequisites_present"])
            self.assertFalse(result["ready"])
            with self.assertRaises(PermissionError):
                require_verified_isolation(result)

    def test_invalid_report_denied(self):
        with self.assertRaises(TypeError):
            require_verified_isolation(None)


if __name__ == "__main__":
    unittest.main()
