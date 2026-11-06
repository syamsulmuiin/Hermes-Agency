import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agency.systemd_jobs import run_systemd_job


class SystemdJobsTests(unittest.TestCase):
    def test_arbitrary_command_denied(self):
        with self.assertRaises(PermissionError):
            run_systemd_job("/bin/sh")

    def test_bad_timeout_denied(self):
        with self.assertRaises(ValueError):
            run_systemd_job("noop", 0)

    @patch("agency.systemd_jobs.os.geteuid", return_value=995)
    def test_agent_cannot_invoke_systemd(self, uid):
        with self.assertRaises(PermissionError):
            run_systemd_job("noop")

    @patch("agency.systemd_jobs.os.geteuid", return_value=0)
    @patch("agency.systemd_jobs.shutil.which", return_value=None)
    def test_missing_runner_denied(self, which, uid):
        with self.assertRaises(PermissionError):
            run_systemd_job("noop")

    @patch("agency.systemd_jobs.os.geteuid", return_value=0)
    @patch("agency.systemd_jobs.shutil.which", return_value="/usr/bin/systemd-run")
    @patch("agency.systemd_jobs.subprocess.run")
    def test_real_process_invocation_is_restricted(self, runner, which, uid):
        runner.return_value = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        result = run_systemd_job("noop")
        argv = runner.call_args.args[0]
        self.assertIn("PrivateNetwork=yes", argv)
        self.assertIn("DynamicUser=yes", argv)
        self.assertIn("MemoryMax=128M", argv)
        self.assertIn("CapabilityBoundingSet=", argv)
        self.assertEqual(argv[-1], "/usr/bin/true")
        self.assertFalse(result["agent_tools_enabled"])

    @patch("agency.systemd_jobs.os.geteuid", return_value=0)
    @patch("agency.systemd_jobs.shutil.which", return_value="/usr/bin/systemd-run")
    @patch("agency.systemd_jobs.subprocess.run")
    def test_host_denial_has_no_fallback(self, runner, which, uid):
        runner.return_value = SimpleNamespace(returncode=1, stdout=b"", stderr=b"denied")
        with self.assertRaises(PermissionError):
            run_systemd_job("noop")
        self.assertEqual(runner.call_count, 1)


if __name__ == "__main__":
    unittest.main()
