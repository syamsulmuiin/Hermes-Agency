import os
import socket
import threading
import unittest
from unittest.mock import Mock

from agency.trusted_ack import read_ack, serve_with_ack


class TrustedAckTests(unittest.TestCase):
    def test_denial_has_no_exception_details(self):
        a, b = socket.socketpair()
        try:
            boundary = Mock()
            b.sendall(b"invalid")
            b.shutdown(socket.SHUT_WR)
            self.assertEqual(
                serve_with_ack(a, boundary, frozenset({os.getuid()})), "denied"
            )
            with self.assertRaises(PermissionError):
                read_ack(b)
            boundary.submit_stage.assert_not_called()
        finally:
            a.close()
            b.close()

    def test_accepted_request(self):
        a, b = socket.socketpair()
        try:
            boundary = Mock()
            request = (
                b'{"task_id":"task","agent":"ceo","result":'
                b'{"completed":[],"output":[],"notes":[],"blockers":[]},'
                b'"worker_credential":"token"}'
            )
            b.sendall(request)
            b.shutdown(socket.SHUT_WR)
            self.assertEqual(
                serve_with_ack(a, boundary, frozenset({os.getuid()})), "accepted"
            )
            self.assertTrue(read_ack(b))
            boundary.submit_stage.assert_called_once()
        finally:
            a.close()
            b.close()

    def test_truncated_ack_fails_closed(self):
        a, b = socket.socketpair()
        try:
            a.sendall(b'{"status":"accepted"}')
            a.shutdown(socket.SHUT_WR)
            with self.assertRaises(PermissionError):
                read_ack(b)
        finally:
            a.close()
            b.close()
