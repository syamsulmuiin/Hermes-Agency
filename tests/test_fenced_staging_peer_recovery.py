"""Isolated staging peer and recovery protocol tests (no real systemd)."""
import os
import socket
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from agency.fenced_staging_broker import unit_for_grant
from agency.fenced_staging_peer import root_stop_session, trusted_peer_session
from agency.fenced_staging_recovery import recover_staging


class StagingPeerProtocolTests(unittest.TestCase):
    def test_stop_request_is_bound_to_verified_grant(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        claims = {"id": "a" * 64}
        unit = unit_for_grant(claims["id"])
        observed = []
        def root():
            with patch("agency.fenced_staging_peer.verify_broker_grant",
                       return_value=claims):
                observed.append(root_stop_session(
                    left, {"grant": "fixture"}, b"k" * 32,
                    stop_unit=lambda u: observed.append(u)))
        thread = threading.Thread(target=root)
        thread.start()
        from agency.trusted_lease_ipc import _send, _read_line
        import json
        _send(right, {"op": "stop", "unit": unit})
        self.assertEqual(json.loads(_read_line(right)),
                         {"status": "verified", "unit": unit})
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(observed, [unit, unit])

    def test_wrong_unit_never_stopped(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        from agency.trusted_lease_ipc import _send
        _send(right, {"op": "stop", "unit": unit_for_grant("b" * 64)})
        with patch("agency.fenced_staging_peer.verify_broker_grant",
                   return_value={"id": "a" * 64}):
            with self.assertRaises(PermissionError):
                root_stop_session(left, {}, b"k" * 32,
                                  stop_unit=lambda _: self.fail("stop called"))

    def test_trusted_peer_rejects_root(self):
        with patch("agency.fenced_staging_peer.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                trusted_peer_session(None, None, "", b"")


@unittest.skipUnless(os.geteuid() == 0, "Root-only staging journal")
class StagingRecoveryTests(unittest.TestCase):
    def test_independent_recovery_and_gate(self):
        from agency.fenced_unit_journal import register_before_launch
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            journal = os.path.join(folder, "owned.sqlite")
            with sqlite3.connect(journal) as db:
                db.execute("CREATE TABLE owned_units(unit TEXT PRIMARY KEY, state TEXT NOT NULL)")
            os.chmod(journal, 0o600)
            unit = unit_for_grant("c" * 64)
            register_before_launch(journal, unit)
            stopped = []
            with patch("agency.fenced_unit_journal.stop_and_verify_unit",
                       side_effect=lambda u: stopped.append(u)):
                # recover_owned_units default callback is bound at definition
                # time; patch the staging recovery dependency instead.
                with patch("agency.fenced_staging_serialization.recover_owned_units",
                           side_effect=lambda p: self._recover(p, stopped)):
                    self.assertEqual(recover_staging(journal), (unit,))
            self.assertEqual(stopped, [unit])

    @staticmethod
    def _recover(path, stopped):
        from agency.fenced_unit_journal import recover_owned_units
        return recover_owned_units(path, stop_unit=lambda u: stopped.append(u))


if __name__ == "__main__":
    unittest.main()
