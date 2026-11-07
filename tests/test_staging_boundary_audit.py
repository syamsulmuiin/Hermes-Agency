"""Regression checks for read-only staging fixture boundary audit."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from agency import staging_boundary_audit as audit


class StagingBoundaryAuditTests(unittest.TestCase):
    def test_expected_fixture_contract_remains_no_go(self):
        output = io.StringIO()
        with redirect_stdout(output):
            audit.audit()
        result = output.getvalue()
        self.assertIn("STAGING_FIXTURE_PATH_ISOLATION=PASS", result)
        self.assertIn("STAGING_RUNTIME_ISOLATION=NOT_ATTESTED", result)
        self.assertIn("STAGING_OPERATOR_END_TO_END=NOT_TESTED", result)
        self.assertIn("PRODUCTION_CUTOVER_GO=NO", result)

    def test_unexpected_base_denied(self):
        with patch.object(audit.replay, "BASE", "/var/lib/hermes-broker"):
            with self.assertRaises(PermissionError):
                audit.audit()

    def test_unpinned_unit_prefix_denied(self):
        with patch.object(audit.cutover, "OLD", "hermes-signed-broker.service"):
            with self.assertRaises(PermissionError):
                audit.audit()


if __name__ == "__main__":
    unittest.main()
