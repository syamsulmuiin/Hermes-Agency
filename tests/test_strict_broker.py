"""Fail-closed production broker mode must never bind or execute."""
import unittest
from unittest.mock import patch

from agency.supervised_broker import serve_forever


class StrictBrokerTests(unittest.TestCase):
    @patch("agency.supervised_broker.socket.socket")
    def test_strict_mode_refuses_before_socket(self, socket_factory):
        with self.assertRaisesRegex(PermissionError, "not installed"):
            serve_forever("/run/test.sock", 1001, 1001, "/tmp/ledger",
                          "/tmp/db", "/tmp/key", require_fenced=True)
        socket_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
