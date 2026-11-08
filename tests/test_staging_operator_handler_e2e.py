"""Isolated staging operator-handler E2E smoke tests."""
import unittest
from unittest.mock import patch
from agency import staging_operator_handler_e2e as target


class StagingOperatorHandlerTests(unittest.TestCase):
    def test_rejects_nonroot_fixture(self):
        with patch.object(target.os, "geteuid", return_value=1000):
            with self.assertRaises(PermissionError):
                target.exercise()

    def test_failure_remains_no_go(self):
        with patch.object(target, "exercise", side_effect=PermissionError):
            self.assertEqual(target.main(["--isolated"]), 2)

    def test_fixture_never_calls_real_broker(self):
        self.assertIn("Broker execution forbidden", target.CHILD)
        self.assertIn("No real approval permitted", target.CHILD)


if __name__ == "__main__":
    unittest.main()
