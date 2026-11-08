"""Regression coverage for non-authorizing operator socket rejection."""
import unittest
from unittest.mock import patch
from agency import live_operator_socket_rejection_probe as target


class LiveSocketProbeTests(unittest.TestCase):
    def test_probe_has_no_approval_fields(self):
        import inspect
        source = inspect.getsource(target.probe)
        self.assertIn('__attestation_invalid_action__', source)
        self.assertNotIn('operator_secret_hex', source)
        self.assertNotIn('approve_and_execute', source)

    def test_failure_never_authorizes(self):
        with patch.object(target, "probe", side_effect=PermissionError):
            self.assertEqual(target.main(["--read-only-rejection"]), 2)


if __name__ == "__main__":
    unittest.main()
