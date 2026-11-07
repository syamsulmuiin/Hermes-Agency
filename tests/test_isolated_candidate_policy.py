"""Isolated candidate path policy regression; no production state accessed."""
import unittest
from unittest.mock import patch

from agency.fenced_broker_candidate import serve_candidate
from agency.fenced_staging_launcher import run_staging_session


class IsolatedCandidatePolicyTests(unittest.TestCase):
    def test_reject_production_path_before_any_io(self):
        with self.assertRaises(PermissionError):
            serve_candidate(
                "/run/hermes-broker/fenced-candidate.sock", 1001, 1001,
                "/run/hermes-staging/ledger.sqlite",
                "/run/hermes-staging/owned.sqlite",
                "/run/hermes-staging/trusted.sqlite",
                "/run/hermes-staging/key", isolated_candidate=True)

    def test_reject_production_ledger(self):
        with self.assertRaises(PermissionError):
            serve_candidate(
                "/run/hermes-staging/candidate.sock", 1001, 1001,
                "/var/lib/hermes-broker/ledger.sqlite",
                "/run/hermes-staging/owned.sqlite",
                "/run/hermes-staging/trusted.sqlite",
                "/run/hermes-staging/key", isolated_candidate=True)

    def test_reject_ambiguous_launcher_profiles(self):
        with patch("agency.fenced_staging_launcher.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                run_staging_session({}, b"x" * 64,
                    "/run/hermes-staging/owned.sqlite",
                    "/run/hermes-staging/trusted.sqlite",
                    trusted_uid=1001, trusted_gid=1001,
                    ledger="/run/hermes-staging/ledger.sqlite",
                    production_candidate=True, isolated_candidate=True)


if __name__ == "__main__":
    unittest.main()
