"""Read-only regression documenting the still-open operator systemd bypass."""
import inspect
import unittest

from agency import systemd_jobs


class DirectSystemdBypassInventory(unittest.TestCase):
    def test_direct_operator_executor_is_not_misreported_as_fenced(self):
        source = inspect.getsource(systemd_jobs.run_systemd_job)
        self.assertIn("subprocess.run", source)
        self.assertNotIn("staging_broker_job", source)
        self.assertNotIn("register_before_launch", source)
        self.assertNotIn("broker_fenced_job", source)

    def test_direct_executor_still_denies_nonroot(self):
        from unittest.mock import patch
        with patch("agency.systemd_jobs.os.geteuid", return_value=1000):
            with self.assertRaises(PermissionError):
                systemd_jobs.run_systemd_job("noop")


if __name__ == "__main__":
    unittest.main()
