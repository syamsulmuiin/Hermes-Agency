"""Fail-closed tests for Linux sandbox probe runner."""
import unittest
from unittest.mock import patch
from agency.linux_sandbox import run_isolated_probe


class LinuxSandboxTests(unittest.TestCase):
    def test_rejects_invalid_timeout(self):
        for timeout in (0, 31, True, "3"):
            with self.assertRaises(ValueError):
                run_isolated_probe(timeout)

    @patch("agency.linux_sandbox.os.geteuid", return_value=0)
    def test_refuses_root(self, unused):
        with self.assertRaises(PermissionError):
            run_isolated_probe()

    @patch("agency.linux_sandbox.os.geteuid", return_value=1000)
    @patch("agency.linux_sandbox.subprocess.run")
    def test_no_unsandboxed_fallback(self, runner, unused):
        runner.return_value.returncode = 1
        runner.return_value.stdout = ""
        with self.assertRaises(PermissionError):
            run_isolated_probe()
        self.assertEqual(runner.call_count, 1)

    @patch("agency.linux_sandbox.os.geteuid", return_value=1000)
    @patch("agency.linux_sandbox.subprocess.run")
    def test_rejects_forged_evidence(self, runner, unused):
        runner.return_value.returncode = 0
        runner.return_value.stdout = '{"root_empty":true,"host_files_absent":true,"pid":99,"uid":0}'
        with self.assertRaises(PermissionError):
            run_isolated_probe()


if __name__ == "__main__":
    unittest.main()
