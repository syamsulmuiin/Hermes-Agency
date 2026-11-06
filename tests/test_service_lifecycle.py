import socket
import unittest
from unittest.mock import patch

from agency.service_lifecycle import serve_forever


class ServiceLifecycleTests(unittest.TestCase):
    def test_idle_timeout_does_not_terminate_service(self):
        outcomes = [socket.timeout(), "accepted", socket.timeout(), "denied"]
        calls = []

        def run(*args):
            outcome = outcomes.pop(0)
            calls.append(outcome)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch("agency.service_lifecycle.run_service", side_effect=run):
            handled = serve_forever(
                "/socket", "/state", "/db", "/keys", 2001,
                frozenset({2002}), b"x" * 64,
                should_stop=lambda: len(calls) >= 4
            )
        self.assertEqual(handled, 2)

    def test_unexpected_failure_propagates_to_supervisor(self):
        with patch("agency.service_lifecycle.run_service",
                   side_effect=PermissionError("unsafe")):
            with self.assertRaises(PermissionError):
                serve_forever("/socket", "/state", "/db", "/keys",
                              2001, frozenset({2002}), b"x" * 64)

    def test_stop_before_start(self):
        with patch("agency.service_lifecycle.run_service") as runner:
            self.assertEqual(serve_forever(
                "/socket", "/state", "/db", "/keys", 2001,
                frozenset({2002}), b"x" * 64,
                should_stop=lambda: True
            ), 0)
            runner.assert_not_called()
