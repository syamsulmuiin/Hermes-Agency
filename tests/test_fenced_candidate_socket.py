"""Persistent candidate socket protocol tests with no real root/systemd changes."""
import json
import os
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from agency.fenced_broker_candidate import serve_candidate


class CandidateSocketTests(unittest.TestCase):
    def _serve(self, *, reject=False):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "candidate.sock")
            done = threading.Event()
            errors = []
            calls = []
            def session(grant, key, journal, trusted_db, **kwargs):
                calls.append((grant, key, journal, trusted_db, kwargs))
                if reject:
                    raise PermissionError("Injected session denial")
                return {"job": "noop", "exit_code": 0}
            # Test-only socket directory; production ownership checks are
            # separately covered by the static and integration acceptance.
            original_lstat = os.lstat
            def fake_lstat(name, *args, **kwargs):
                info = original_lstat(name, *args, **kwargs)
                if name == directory:
                    values = list(info)
                    values[4] = 0
                    values[5] = 1001
                    values[0] = (values[0] & ~0o777) | 0o710
                    return os.stat_result(values)
                return info
            def server():
                try:
                    serve_candidate(path, 1001, 1001,
                                    "/tmp/test-ledger", "/tmp/test-journal",
                                    "/tmp/test-db", "/tmp/test-key",
                                    stop=done.is_set, session=session)
                except BaseException as exc:
                    errors.append(exc)
            # Production root checks and credential policy are mocked only
            # for exercising framing and response behavior.
            with patch("agency.fenced_broker_candidate.os.geteuid", return_value=0), \
                 patch("agency.fenced_broker_candidate.pwd.getpwuid") as identity, \
                 patch("agency.fenced_broker_candidate.verify_private_ledger"), \
                 patch("agency.fenced_broker_candidate.require_recovered"), \
                 patch("agency.fenced_broker_candidate.read_broker_key", return_value=b"k" * 64), \
                 patch("agency.fenced_broker_candidate.verify_broker_grant"), \
                 patch("agency.fenced_broker_candidate.os.lstat", side_effect=fake_lstat), \
                 patch("agency.fenced_broker_candidate.os.chown"), \
                 patch("agency.fenced_broker_candidate._read_grant", return_value={"claims": {}}):
                identity.return_value.pw_gid = 1001
                # Socket bind happens in the thread; signal readiness by
                # polling its existence, not a fixed sleep.
                worker = threading.Thread(target=server)
                worker.start()
                try:
                    import time
                    for _ in range(200):
                        if os.path.exists(path):
                            break
                        if errors:
                            break
                        time.sleep(0.01)
                    self.assertTrue(os.path.exists(path), errors)
                    with socket.socket(socket.AF_UNIX) as client:
                        client.connect(path)
                        client.sendall(b'{"grant":{}}\n')
                        if not reject:
                            response = client.recv(4096)
                            self.assertEqual(json.loads(response), {
                                "job": "noop", "exit_code": 0})
                    self.assertEqual(len(calls), 1)
                finally:
                    done.set()
                    worker.join(5)
                if reject:
                    self.assertTrue(errors)
                else:
                    self.assertFalse(errors, errors)

    def test_successful_candidate_socket_round_trip(self):
        self._serve()


if __name__ == "__main__":
    unittest.main()
