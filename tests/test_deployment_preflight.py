import os
import tempfile
import unittest
from unittest.mock import patch

from agency.deployment_preflight import verify_deployment


class DeploymentPreflightTests(unittest.TestCase):
    def test_valid_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            state = os.path.join(root, "private")
            transport = os.path.join(root, "transport")
            keys = os.path.join(state, "keys")
            database = os.path.join(state, "state.db")
            os.mkdir(state, 0o700)
            os.mkdir(keys, 0o700)
            os.mkdir(transport, 0o710)
            with open(database, "wb"):
                pass
            os.chmod(database, 0o600)
            with patch("agency.deployment_preflight.os.geteuid",
                       return_value=os.geteuid() or 1000):
                # Root-run CI is intentionally denied; non-root CI validates layout.
                if os.geteuid() == 0:
                    with self.assertRaises(PermissionError):
                        verify_deployment(transport, state, database, keys,
                                          os.getegid(), frozenset({1001}))
                else:
                    self.assertTrue(verify_deployment(
                        transport, state, database, keys, os.getegid(),
                        frozenset({os.geteuid() + 1})
                    ))

    def test_root_denied(self):
        with patch("agency.deployment_preflight.os.geteuid", return_value=0):
            with self.assertRaises(PermissionError):
                verify_deployment("/none", "/none", "/none", "/none", 1000,
                                  frozenset({1001}))

    def test_same_uid_denied(self):
        uid = os.geteuid() or 1000
        with patch("agency.deployment_preflight.os.geteuid", return_value=uid):
            with self.assertRaises(PermissionError):
                verify_deployment("/none", "/none", "/none", "/none", 1000,
                                  frozenset({uid}))

    def test_invalid_group_denied(self):
        uid = os.geteuid() or 1000
        with patch("agency.deployment_preflight.os.geteuid", return_value=uid):
            with self.assertRaises(ValueError):
                verify_deployment("/none", "/none", "/none", "/none", -1,
                                  frozenset({uid + 1}))
