"""Isolated independent recovery tests; never call real systemctl."""
import subprocess
import unittest
from unittest.mock import patch

from agency.fenced_unit_recovery import discover_fenced_units, recover_fenced_units

A = "hermes-fenced-" + "a" * 32 + ".service"
B = "hermes-fenced-" + "b" * 32 + ".service"


def fake_output(text, status=0):
    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, status, text.encode(), b"")
    return runner


class FencedUnitRecoveryTests(unittest.TestCase):
    def test_discovers_only_fenced_units(self):
        runner = fake_output(
            A + " loaded active running test\n"
            + "hermes-agency.service loaded active running test\n"
            + "● " + B + " loaded failed failed test\n")
        self.assertEqual(discover_fenced_units(runner), (A, B))

    def test_rejects_malformed_fenced_unit(self):
        with self.assertRaises(PermissionError):
            discover_fenced_units(fake_output(
                "hermes-fenced-unsafe.service loaded active running test\n"))

    def test_enumeration_failure_fails_closed(self):
        with self.assertRaises(PermissionError):
            discover_fenced_units(fake_output("", status=1))

    @patch("agency.fenced_unit_recovery.os.geteuid", return_value=0)
    def test_stopped_broker_recovers_all(self, _):
        seen = []
        units = recover_fenced_units(
            broker_stopped=True,
            runner=fake_output(A + " loaded active running test\n"),
            stop_unit=seen.append)
        self.assertEqual(units, (A,))
        self.assertEqual(seen, [A])

    @patch("agency.fenced_unit_recovery.os.geteuid", return_value=0)
    def test_refuses_recovery_without_stopped_broker(self, _):
        with self.assertRaises(PermissionError):
            recover_fenced_units(
                broker_stopped=False,
                runner=lambda *args, **kwargs: self.fail("enumeration called"))

    @patch("agency.fenced_unit_recovery.os.geteuid", return_value=0)
    def test_failed_cleanup_denies_success(self, _):
        def stop(unit):
            raise PermissionError("still running")
        with self.assertRaises(PermissionError):
            recover_fenced_units(
                broker_stopped=True,
                runner=fake_output(A + " loaded active running test\n"),
                stop_unit=stop)


if __name__ == "__main__":
    unittest.main()
