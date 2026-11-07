"""Regression tests for systemd transient-unit stop verification."""
import subprocess
import unittest
from unittest.mock import patch

from agency.fenced_systemd_supervisor import stop_and_verify_unit

UNIT = "hermes-fenced-" + "a" * 32 + ".service"


def response(state, job="0", pid="0", code=0):
    return subprocess.CompletedProcess(
        args=[], returncode=code,
        stdout=("ActiveState=" + state + "\nSubState=dead\nJob=" + job +
                "\nMainPID=" + pid + "\n").encode(), stderr=b"")


class CollectedUnitTests(unittest.TestCase):
    def test_already_collected_unit_needs_no_stop(self):
        with patch("agency.fenced_systemd_supervisor._systemctl",
                   return_value=response("inactive")) as ctl:
            self.assertTrue(stop_and_verify_unit(UNIT))
            self.assertEqual(ctl.call_count, 1)

    def test_active_unit_stop_and_verify(self):
        with patch("agency.fenced_systemd_supervisor._systemctl",
                   side_effect=[response("active", pid="123"),
                                subprocess.CompletedProcess([], 0, b"", b""),
                                response("inactive")]) as ctl:
            self.assertTrue(stop_and_verify_unit(UNIT))
            self.assertEqual(ctl.call_count, 3)

    def test_failed_stop_with_active_unit_denied(self):
        with patch("agency.fenced_systemd_supervisor._systemctl",
                   side_effect=[response("active", pid="123"),
                                subprocess.CompletedProcess([], 1, b"", b""),
                                response("active", pid="123")]):
            with self.assertRaises(PermissionError):
                stop_and_verify_unit(UNIT)

    def test_missing_systemd_status_denied(self):
        with patch("agency.fenced_systemd_supervisor._systemctl",
                   return_value=response("inactive", code=1)):
            with self.assertRaises(PermissionError):
                stop_and_verify_unit(UNIT)


if __name__ == "__main__":
    unittest.main()
