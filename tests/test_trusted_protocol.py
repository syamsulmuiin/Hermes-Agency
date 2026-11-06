import json
import unittest
from agency.trusted_protocol import parse_stage_request


class TrustedProtocolTests(unittest.TestCase):
    def test_valid_request(self):
        request = {
            "task_id": "task-1", "agent": "ceo",
            "worker_credential": "test-credential",
            "result": {"completed": [], "output": [], "notes": [], "blockers": []},
        }
        self.assertEqual(parse_stage_request(json.dumps(request).encode()), request)

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            parse_stage_request(b"invalid")

    def test_extra_fields(self):
        request = {
            "task_id": "t", "agent": "ceo", "worker_credential": "test",
            "result": {"completed": [], "output": [], "notes": [], "blockers": []},
            "unexpected": True,
        }
        with self.assertRaises(ValueError):
            parse_stage_request(json.dumps(request).encode())
