"""Acceptance phase ordering and fail-closed simulation tests."""
import unittest

from agency.staging_acceptance_simulation import PHASES, simulate


class AcceptanceSimulationTests(unittest.TestCase):
    def test_all_phases_simulated_never_authorize(self):
        result = simulate({name: lambda: True for name in PHASES})
        self.assertTrue(result["simulation_complete"])
        self.assertFalse(result["real_pid1_tested"])
        self.assertFalse(result["execute_authorized"])

    def test_every_failure_injection_stops_before_next_phase(self):
        for index, failed in enumerate(PHASES):
            with self.subTest(phase=failed):
                visited = []
                def check(name):
                    def run():
                        visited.append(name)
                        return name != failed
                    return run
                result = simulate({name: check(name) for name in PHASES})
                self.assertEqual(visited, list(PHASES[:index + 1]))
                self.assertFalse(result["simulation_complete"])
                self.assertFalse(result["execute_authorized"])
                self.assertEqual(result["phases"][-1]["result"], "DENIED")

    def test_missing_phase_denied(self):
        result = simulate({})
        self.assertFalse(result["simulation_complete"])
        self.assertEqual(result["phases"][0]["reason"], "KeyError")

    def test_exception_denied(self):
        def fail():
            raise RuntimeError("injected crash")
        result = simulate({PHASES[0]: fail})
        self.assertFalse(result["simulation_complete"])
        self.assertFalse(result["execute_authorized"])


if __name__ == "__main__":
    unittest.main()
