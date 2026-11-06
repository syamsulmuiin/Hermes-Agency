import unittest
from unittest.mock import patch

from agency.sandbox_validation import validate_candidates, require_validated_executor


class SandboxValidationTests(unittest.TestCase):
    def test_invalid_timeout(self):
        for value in (0, 11, True, "5"):
            with self.assertRaises(ValueError):
                validate_candidates(value)

    @patch("agency.sandbox_validation.os.geteuid", return_value=1000)
    @patch("agency.sandbox_validation.run_isolated_probe")
    @patch("agency.sandbox_validation.sandbox_probe")
    def test_both_probes_pass_still_denies_execution(self, bwrap, rootless, uid):
        result = validate_candidates()
        self.assertTrue(result["candidates"]["rootless_namespace"]["probe_passed"])
        self.assertTrue(result["candidates"]["bubblewrap"]["probe_passed"])
        self.assertFalse(result["agent_tools_enabled"])
        self.assertIsNone(result["selected"])
        with self.assertRaises(PermissionError):
            require_validated_executor(result)

    @patch("agency.sandbox_validation.os.geteuid", return_value=1000)
    @patch("agency.sandbox_validation.run_isolated_probe", side_effect=PermissionError("private details"))
    @patch("agency.sandbox_validation.sandbox_probe", side_effect=RuntimeError("bubblewrap not installed"))
    def test_denied_host_reports_safe_reasons(self, bwrap, rootless, uid):
        result = validate_candidates()
        self.assertEqual(result["candidates"]["rootless_namespace"]["reason"],
                         "host_policy_or_isolation_denied")
        self.assertEqual(result["candidates"]["bubblewrap"]["reason"], "backend_missing")
        self.assertNotIn("private details", str(result))

    @patch("agency.sandbox_validation.os.geteuid", return_value=0)
    @patch("agency.sandbox_validation.run_isolated_probe")
    @patch("agency.sandbox_validation.sandbox_probe")
    def test_root_never_launches_probe(self, bwrap, rootless, uid):
        result = validate_candidates()
        rootless.assert_not_called()
        bwrap.assert_not_called()
        self.assertFalse(result["agent_tools_enabled"])

    def test_bad_report_denied(self):
        with self.assertRaises(TypeError):
            require_validated_executor(None)


if __name__ == "__main__":
    unittest.main()
