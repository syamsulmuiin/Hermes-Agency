"""Tests for passive sidecar kernel-lock observation."""
import unittest
from agency.passive_sidecar_lock_observation import matching_locks, observe


class PassiveSidecarLockTests(unittest.TestCase):
    def test_matches_pid_inode_and_device(self):
        device = 25
        lines = [
            "1: FLOCK ADVISORY READ 123 00:19:221186 0 EOF",
            "2: FLOCK ADVISORY WRITE 456 00:19:221186 0 EOF",
            "3: POSIX ADVISORY READ 123 00:19:221186 0 EOF",
        ]
        self.assertEqual(matching_locks(lines, 123, device, 221186),
                         [{"mode": "READ", "pid": 123}])

    def test_missing_observation_remains_unattested(self):
        state = {"sidecar_pid": 123, "lock_device": 25,
                 "lock_inode": 221186, "snapshot": "/test",
                 "freeze_present": True}
        result = observe(duration=0.01, interval=0.005,
                         reader=lambda: [], runtime=lambda: dict(state),
                         clock=iter([0, 1]).__next__,
                         sleeper=lambda _: None)
        self.assertEqual(result["live_admission_lock_participation"], "NOT_ATTESTED")
        self.assertFalse(result["cutover_authorized"])

    def test_shared_lock_is_observation_only(self):
        state = {"sidecar_pid": 123, "lock_device": 25,
                 "lock_inode": 221186, "snapshot": "/test",
                 "freeze_present": True}
        result = observe(duration=0.01, interval=0.005,
                         reader=lambda: ["1: FLOCK ADVISORY READ 123 00:19:221186 0 EOF"],
                         runtime=lambda: dict(state),
                         clock=iter([0, 1]).__next__,
                         sleeper=lambda _: None)
        self.assertEqual(result["live_admission_lock_participation"],
                         "OBSERVED_SHARED_LOCK_NOT_AUTHORIZED")
        self.assertFalse(result["cutover_authorized"])


if __name__ == "__main__":
    unittest.main()
