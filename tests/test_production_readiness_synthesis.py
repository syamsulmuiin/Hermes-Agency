"""Fail-closed tests for production readiness synthesis."""
import unittest
from agency.production_readiness_synthesis import collect


class ReadinessSynthesisTests(unittest.TestCase):
    def test_successful_read_only_checks_do_not_authorize(self):
        result = collect(lambda: {"cutover_authorized": False, "runtime_identity": "PASS"},
                         lambda: {"cutover_authorized": False, "installed_recovery_wiring": "PASS"})
        self.assertEqual(result["decision"], "NO_GO")
        self.assertFalse(result["production_cutover_go"])
        self.assertTrue(all(x == "NOT_ATTESTED" for x in result["production_blockers"].values()))
        self.assertEqual(result["fresh_read_only"]["runtime_identity"]["status"], "PASS")

    def test_probe_failure_fails_closed(self):
        def failed():
            raise PermissionError("no")
        result = collect(failed, failed)
        self.assertEqual(result["fresh_read_only"]["runtime_identity"]["status"], "UNVERIFIED")
        self.assertEqual(result["decision"], "NO_GO")

    def test_unexpected_authorization_is_rejected(self):
        result = collect(lambda: {"cutover_authorized": True},
                         lambda: {"cutover_authorized": False})
        self.assertEqual(result["fresh_read_only"]["runtime_identity"]["status"], "UNVERIFIED")
        self.assertFalse(result["production_cutover_go"])


if __name__ == "__main__":
    unittest.main()
