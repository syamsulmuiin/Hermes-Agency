"""Opt-in broker systemd lifecycle tests; no real systemctl or systemd-run."""
import socket
import unittest
from unittest.mock import patch

from agency.fenced_systemd_supervisor import supervised_fenced_unit


class FencedBrokerUnitLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.grant_id = "a" * 64

    def tearDown(self):
        self.a.close()
        self.b.close()

    @patch("agency.fenced_systemd_supervisor.stop_and_verify_unit")
    def test_success_requires_stop_verification(self, stop):
        observed = []
        def runner(job, fence, unit):
            observed.append((job, fence, unit))
            return {"exit_code": 0}
        result = supervised_fenced_unit("noop", self.grant_id, self.a, runner)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(observed[0][0], "noop")
        self.assertIs(observed[0][1], self.a)
        self.assertEqual(stop.call_args.args[0], observed[0][2])

    @patch("agency.fenced_systemd_supervisor.stop_and_verify_unit")
    def test_disconnect_failure_always_stops_unit(self, stop):
        def runner(job, fence, unit):
            raise PermissionError("Fence disconnected")
        with self.assertRaisesRegex(PermissionError, "disconnected"):
            supervised_fenced_unit("noop", self.grant_id, self.a, runner)
        stop.assert_called_once()

    @patch("agency.fenced_systemd_supervisor.stop_and_verify_unit")
    def test_failed_cleanup_never_returns_success(self, stop):
        stop.side_effect = PermissionError("Still active")
        with self.assertRaisesRegex(PermissionError, "Still active"):
            supervised_fenced_unit(
                "noop", self.grant_id, self.a,
                lambda job, fence, unit: {"exit_code": 0})

    def test_invalid_job_never_runs(self):
        with self.assertRaises(PermissionError):
            supervised_fenced_unit(
                "shell", self.grant_id, self.a,
                lambda job, fence, unit: self.fail("runner invoked"))


if __name__ == "__main__":
    unittest.main()
