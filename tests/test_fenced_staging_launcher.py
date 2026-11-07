"""Staging launcher fail-closed input tests; no processes or systemd launched."""
import unittest
from unittest.mock import patch

from agency.fenced_staging_launcher import _staging_path, run_staging_session


class StagingLauncherBoundaryTests(unittest.TestCase):
    def test_only_isolated_runtime_paths(self):
        for path in ("/opt/hermes-agency/data", "/var/lib/hermes-agency/db",
                     "/run/hermes-staging/../hermes-agency/db",
                     "relative", "/run/hermes-staging/../../etc/passwd"):
            with self.assertRaises(PermissionError):
                _staging_path(path)
        self.assertEqual(_staging_path("/run/hermes-staging/test/owned.sqlite"),
                         "/run/hermes-staging/test/owned.sqlite")

    def test_nonroot_denied_before_process_creation(self):
        with patch("agency.fenced_staging_launcher.os.geteuid", return_value=1000):
            with self.assertRaises(PermissionError):
                run_staging_session({}, b"k" * 32,
                    "/run/hermes-staging/test/owned.sqlite",
                    "/run/hermes-staging/test/trusted.sqlite",
                    trusted_uid=65534, trusted_gid=65534)

    def test_root_identity_and_key_required(self):
        with patch("agency.fenced_staging_launcher.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                run_staging_session({}, b"k" * 32,
                    "/run/hermes-staging/test/owned.sqlite",
                    "/run/hermes-staging/test/trusted.sqlite",
                    trusted_uid=0, trusted_gid=65534)
            with self.assertRaises(PermissionError):
                run_staging_session({}, b"short",
                    "/run/hermes-staging/test/owned.sqlite",
                    "/run/hermes-staging/test/trusted.sqlite",
                    trusted_uid=65534, trusted_gid=65534)


if __name__ == "__main__":
    unittest.main()
