"""Mocked unit lifecycle tests: never call host systemctl."""
import subprocess
import unittest
from unittest.mock import patch

from agency.fenced_systemd_supervisor import stop_and_verify_unit

UNIT = "hermes-fenced-" + "a" * 32 + ".service"


def reply(code=0, output=b""):
    return subprocess.CompletedProcess([], code, output, b"")


class FencedSystemdSupervisorTests(unittest.TestCase):
    def test_reject_unrelated_unit(self):
        with self.assertRaises(PermissionError):
            stop_and_verify_unit("hermes-agency.service")

    @patch("agency.fenced_systemd_supervisor._systemctl")
    def test_stop_requires_inactive_no_job_no_pid(self, call):
        call.return_value = reply(output=b"ActiveState=inactive\nSubState=dead\nJob=\nMainPID=0\n")
        self.assertTrue(stop_and_verify_unit(UNIT))
        self.assertEqual(call.call_count, 1)

    @patch("agency.fenced_systemd_supervisor._systemctl")
    def test_stop_failure_denied(self, call):
        call.return_value = reply(1)
        with self.assertRaises(PermissionError):
            stop_and_verify_unit(UNIT)

    @patch("agency.fenced_systemd_supervisor._systemctl")
    def test_missing_status_denied(self, call):
        call.side_effect = [reply(output=b"ActiveState=active\nJob=0\nMainPID=123\n"), reply(), reply(1)]
        with self.assertRaises(PermissionError):
            stop_and_verify_unit(UNIT)

    @patch("agency.fenced_systemd_supervisor._systemctl")
    def test_active_pid_never_accepted(self, call):
        call.side_effect = [
            reply(output=b"ActiveState=active\nSubState=running\nJob=\nMainPID=123\n"), reply()]
        with patch("agency.fenced_systemd_supervisor.time.monotonic",
                   side_effect=[0, 1]):
            with self.assertRaises(PermissionError):
                stop_and_verify_unit(UNIT, deadline_seconds=0.1)


if __name__ == "__main__":
    unittest.main()
