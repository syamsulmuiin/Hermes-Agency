"""Candidate service preflight must reject unsafe wiring."""
import unittest
from unittest.mock import patch

from agency.fenced_candidate_preflight import check


class CandidatePreflightTests(unittest.TestCase):
    def test_checked_in_candidate_services(self):
        self.assertTrue(check())

    @patch("agency.fenced_candidate_preflight._unit")
    def test_missing_failure_recovery_denied(self, load):
        broker = {"Service": {
            "ExecStart": "agency.fenced_broker_candidate --execute --journal /var/lib/hermes-broker/owned-units.sqlite --socket /run/hermes-broker/fenced-candidate.sock",
            "ExecStartPre": "agency.fenced_startup_gate --journal /var/lib/hermes-broker/owned-units.sqlite",
            "Restart": "no", "User": "root"},
            "Unit": {"OnFailure": "wrong.service"}}
        recovery = {"Service": {
            "ExecStart": "agency.fenced_owned_recovery --journal /var/lib/hermes-broker/owned-units.sqlite --execute",
            "User": "root"}}
        load.side_effect = [broker, recovery]
        with self.assertRaisesRegex(PermissionError, "trigger recovery"):
            check()


if __name__ == "__main__":
    unittest.main()
