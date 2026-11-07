import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.trusted_broker_adapter import _trusted_key, execute_approved_job
from agency.broker_key_rotation import rotate_broker_key


class TrustedBrokerAdapterTests(unittest.TestCase):
    def test_root_cannot_use_trusted_adapter(self):
        with patch("agency.trusted_broker_adapter.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                _trusted_key("/tmp/not-a-key")

    def test_adapter_fails_before_grant_on_invalid_key(self):
        with patch("agency.trusted_broker_adapter._trusted_key",
                   side_effect=PermissionError("key denied")):
            with self.assertRaises(PermissionError):
                execute_approved_job(None, "approval", "task", "noop",
                                     "credential", "lease", "/bad", "/bad")

    def test_rotation_replaces_key_and_invalidates_old_signature(self):
        # Root-only isolated test, without touching production key.
        if os.geteuid() != 0:
            self.skipTest("Requires root")
        import hashlib
        import hmac
        import grp
        from agency.signed_broker_service import provision_broker_key, read_broker_key
        gid = os.getgid()
        if gid <= 0:
            self.skipTest("Requires dedicated non-root trusted group")
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "broker.key")
            provision_broker_key(path, gid)
            old = read_broker_key(path, 1, gid)
            old_sig = hmac.new(old, b"test", hashlib.sha256).digest()
            rotate_broker_key(path, 1, gid)
            new = read_broker_key(path, 1, gid)
            self.assertNotEqual(old, new)
            self.assertNotEqual(old_sig, hmac.new(new, b"test", hashlib.sha256).digest())


if __name__ == "__main__":
    unittest.main()
