"""Integrated cutover success/failure/replay/rollback simulation tests."""
import unittest

from agency.production_cutover_controller import cutover, CutoverError
from agency.production_cutover_simulation import SimulatedAdapter


class CutoverControllerTests(unittest.TestCase):
    def test_success(self):
        adapter = SimulatedAdapter()
        result = cutover(adapter)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(adapter.route, "fenced")
        self.assertFalse(adapter.frozen)
        self.assertEqual(adapter.consumed, {"test-grant"})
        self.assertIn("replay_denied", result.steps)

    def test_each_failure_rolls_back_without_replay_reset(self):
        for failure in ("attest", "freeze", "quiesce", "stop_old",
                        "bootstrap", "start_new", "route_new",
                        "replay_probe", "health"):
            with self.subTest(failure=failure):
                adapter = SimulatedAdapter(fail=failure)
                with self.assertRaises(CutoverError):
                    cutover(adapter)
                self.assertEqual(adapter.route, "legacy")
                self.assertTrue(adapter.legacy)
                self.assertFalse(adapter.frozen)
                self.assertFalse(adapter.quarantined)
                if failure == "health":
                    self.assertEqual(adapter.consumed, {"test-grant"})

    def test_successful_handover_unfreeze_failure_quarantines(self):
        adapter = SimulatedAdapter(fail="unfreeze")
        with self.assertRaisesRegex(CutoverError, "unfreeze failed"):
            cutover(adapter)
        self.assertEqual(adapter.route, "fenced")
        self.assertEqual(adapter.consumed, {"test-grant"})
        self.assertTrue(adapter.quarantined)
        self.assertTrue(adapter.frozen)

    def test_rollback_unfreeze_failure_quarantines(self):
        adapter = SimulatedAdapter(fail="unfreeze")
        def fail_attest():
            raise RuntimeError("Attestation rejected")
        adapter.attest = fail_attest
        with self.assertRaisesRegex(CutoverError, "rollback unverified"):
            cutover(adapter)
        self.assertEqual(adapter.route, "legacy")
        self.assertTrue(adapter.quarantined)
        self.assertTrue(adapter.frozen)

    def test_rollback_failure_quarantines(self):
        adapter = SimulatedAdapter(fail="rollback")
        # Fail at an earlier step and then fail rollback.
        def fail_attest():
            adapter.fail = "rollback"
            raise RuntimeError("Attestation rejected")
        adapter.attest = fail_attest
        with self.assertRaisesRegex(CutoverError, "rollback unverified"):
            cutover(adapter)
        self.assertTrue(adapter.quarantined)
        self.assertTrue(adapter.frozen)


if __name__ == "__main__":
    unittest.main()
