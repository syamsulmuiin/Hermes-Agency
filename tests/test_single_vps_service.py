"""Single-VPS runner tests; no live tools, credentials, or host mutation."""
import os
import tempfile
import unittest
from unittest.mock import patch

from agency.single_vps_service import run_service


class SingleVpsRunnerTests(unittest.TestCase):
    def test_rejects_missing_secret_before_state_access(self):
        with patch("agency.single_vps_service.verify_deployment") as gate:
            with self.assertRaises(ValueError):
                run_service("/no/socket", "/no/state", "/no/db", "/no/keys",
                            2000, frozenset({2001}), b"short")
            gate.assert_not_called()

    def test_rejects_unsafe_layout_before_database_open(self):
        with patch("agency.single_vps_service.verify_deployment",
                   side_effect=PermissionError("unsafe")):
            with patch("agency.single_vps_service.SecureAgencyStore") as store:
                with self.assertRaises(PermissionError):
                    run_service("/no/socket", "/no/state", "/no/db", "/no/keys",
                                2000, frozenset({2001}), b"x" * 64)
                store.assert_not_called()

    def test_service_owns_store_and_closes_on_failure(self):
        with (patch("agency.single_vps_service.verify_deployment"),
              patch("agency.single_vps_service.SecureAgencyStore") as store,
              patch("agency.single_vps_service.WorkflowCoordinator"),
              patch("agency.single_vps_service.PortableAgentRuntime"),
              patch("agency.single_vps_service.TrustedApprovalService"),
              patch("agency.single_vps_service.TrustedAgentExecution"),
              patch("agency.single_vps_service.serve_protected_once",
                    side_effect=PermissionError("transport"))):
            with self.assertRaises(PermissionError):
                run_service("/no/socket", "/no/state", "/no/db", "/no/keys",
                            2000, frozenset({2001}), b"x" * 64)
            store.return_value.close.assert_called_once()
