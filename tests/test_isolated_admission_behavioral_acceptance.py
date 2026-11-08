"""Isolated behavioral acceptance regression tests."""
import unittest
from agency.isolated_admission_behavioral_acceptance import exercise


class IsolatedAdmissionBehaviorTests(unittest.TestCase):
    def test_real_process_contention_and_inode_replacement(self):
        result = exercise()
        self.assertEqual(result["isolated_shared_lock_contention"], "PASS")
        self.assertEqual(result["isolated_exclusive_drain"], "PASS")
        self.assertEqual(result["isolated_inode_replacement_denied"], "PASS")
        self.assertEqual(result["live_sidecar_admission"], "NOT_ATTESTED")
        self.assertEqual(result["production_exclusive_drain"], "NOT_ATTESTED")
        self.assertIs(result["production_mutated"], False)
        self.assertIs(result["cutover_authorized"], False)


if __name__ == "__main__":
    unittest.main()
