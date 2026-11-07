import tempfile
import unittest
from pathlib import Path
from agency.broker_unit_audit import check_unit


class ProductionUnitAuditTests(unittest.TestCase):
    def test_template_hardening(self):
        path = Path(__file__).resolve().parents[1] / "deploy/hermes-signed-broker.service.example"
        self.assertTrue(check_unit(str(path)))

    def test_reject_weakened_unit(self):
        path = Path(__file__).resolve().parents[1] / "deploy/hermes-signed-broker.service.example"
        source = path.read_text()
        with tempfile.TemporaryDirectory() as directory:
            weakened = Path(directory) / "broker.service"
            weakened.write_text(source.replace("ProtectSystem=strict", "ProtectSystem=no"))
            with self.assertRaises(PermissionError):
                check_unit(str(weakened))
