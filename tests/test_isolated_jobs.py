import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agency.isolated_jobs import run_isolated_job


class IsolatedJobsTests(unittest.TestCase):
    def test_rejects_arbitrary_job(self):
        with self.assertRaises(PermissionError):
            run_isolated_job("/bin/sh")

    def test_rejects_invalid_timeout(self):
        with self.assertRaises(ValueError):
            run_isolated_job("noop", timeout=0)

    @patch("agency.isolated_jobs.os.geteuid", return_value=0)
    def test_root_denied(self, unused):
        with self.assertRaises(PermissionError):
            run_isolated_job("noop")

    @patch("agency.isolated_jobs.os.geteuid", return_value=1000)
    @patch("agency.isolated_jobs.shutil.which", return_value=None)
    def test_missing_backend_denied(self, which, uid):
        with self.assertRaises(PermissionError):
            run_isolated_job("noop")

    @patch("agency.isolated_jobs.os.geteuid", return_value=1000)
    @patch("agency.isolated_jobs.shutil.which", return_value="/usr/bin/bwrap")
    @patch("agency.isolated_jobs.os.path.islink", return_value=True)
    @patch("agency.isolated_jobs.os.readlink", side_effect=["usr/bin", "usr/lib", "usr/lib64"])
    @patch("agency.isolated_jobs.subprocess.run")
    def test_fixed_job_uses_namespace_and_never_host_shell(self, runner, readlink, islink, which, uid):
        runner.return_value = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        result = run_isolated_job("noop")
        argv = runner.call_args.args[0]
        self.assertIn("--unshare-all", argv)
        self.assertIn("--clearenv", argv)
        self.assertEqual(argv[-1], "/usr/bin/true")
        self.assertEqual(runner.call_args.kwargs["env"], {})
        self.assertFalse(result["agent_tools_enabled"])

    @patch("agency.isolated_jobs.os.geteuid", return_value=1000)
    @patch("agency.isolated_jobs.shutil.which", return_value="/usr/bin/bwrap")
    @patch("agency.isolated_jobs.os.path.islink", return_value=True)
    @patch("agency.isolated_jobs.os.readlink", side_effect=["usr/bin", "usr/lib", "usr/lib64"])
    @patch("agency.isolated_jobs.subprocess.run")
    def test_failed_backend_has_no_fallback(self, runner, readlink, islink, which, uid):
        runner.return_value = SimpleNamespace(returncode=1, stdout=b"", stderr=b"denied")
        with self.assertRaises(PermissionError):
            run_isolated_job("noop")
        self.assertEqual(runner.call_count, 1)


if __name__ == "__main__":
    unittest.main()
