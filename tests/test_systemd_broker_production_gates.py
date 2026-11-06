import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.systemd_broker import initialize_ledger, verify_private_ledger
from agency.systemd_broker_e2e import run_operator_e2e


class BrokerProductionGatesTests(unittest.TestCase):
    def test_non_root_operator_e2e_denied(self):
        with patch("agency.systemd_broker_e2e.os.geteuid", return_value=995):
            with self.assertRaises(PermissionError):
                run_operator_e2e()

    def test_existing_ledger_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.sqlite"
            path.write_text("do not overwrite")
            with patch("agency.systemd_broker.os.geteuid", return_value=0):
                with self.assertRaises(PermissionError):
                    initialize_ledger(str(path))
            self.assertEqual(path.read_text(), "do not overwrite")

    def test_non_root_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            path.touch(mode=0o600)
            with patch("agency.systemd_broker.os.geteuid", return_value=0):
                with self.assertRaises(PermissionError):
                    verify_private_ledger(str(path))


if __name__ == "__main__":
    unittest.main()
