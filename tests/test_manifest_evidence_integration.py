"""Cross-host manifest injection regression; no production resources used."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency.production_runtime_evidence import capture
from agency.production_recovery_wiring_evidence import inspect
from tests.test_deployment_manifest import BASE


def resolved(manifest):
    return {"identity_resolved": True, "cutover_authorized": False,
            "sandbox_authorized": False, "systemctl": "/custom/systemctl",
            "paths": manifest["paths"], "units": manifest["units"]}


class ManifestEvidenceIntegrationTests(unittest.TestCase):
    def test_recovery_uses_custom_units_and_snapshot(self):
        data = copy.deepcopy(BASE)
        calls = []
        def show(unit):
            calls.append(unit)
            return {"LoadState": "loaded", "WorkingDirectory": data["paths"]["snapshot"],
                    "User": "root", "OnFailure": data["units"]["candidate_recovery"],
                    "Requires": data["units"]["candidate_recovery"],
                    "After": data["units"]["candidate_recovery"],
                    "ExecStartPre": "fenced_startup_gate",
                    "ExecStopPost": "fenced_owned_recovery",
                    "ExecStart": "fenced_owned_recovery"}
        result = inspect(data, resolver=resolved, show=show)
        self.assertEqual(result["installed_recovery_wiring"], "PASS")
        self.assertEqual(calls, [data["units"]["candidate_broker"],
                                 data["units"]["candidate_recovery"]])
        self.assertFalse(result["cutover_authorized"])

    def test_recovery_mismatch_denied(self):
        data = copy.deepcopy(BASE)
        with self.assertRaises(PermissionError):
            inspect(data, resolver=resolved,
                    show=lambda unit: {"LoadState": "loaded", "WorkingDirectory": "/wrong",
                                       "User": "root"})

    def test_runtime_uses_custom_paths_and_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = copy.deepcopy(BASE)
            snapshot = root / "snapshot"
            snapshot.mkdir()
            lock = root / "lock"
            lock.touch()
            lock.chmod(0o640)
            freeze = root / "freeze"
            freeze.touch()
            data["paths"].update(snapshot=str(snapshot), admission_lock=str(lock),
                                 freeze_marker=str(freeze))
            def show(unit, *keys):
                self.assertEqual(unit, data["units"]["sidecar"])
                return {"ActiveState": "active", "MainPID": "12345",
                        "User": data["identities"]["trusted_user"],
                        "WorkingDirectory": str(snapshot),
                        "Environment": "PYTHONPATH=" + str(snapshot)}
            with patch("agency.production_runtime_evidence.os.readlink",
                       return_value=str(snapshot)), patch(
                       "agency.production_runtime_evidence.Path.read_bytes",
                       return_value=bytes([112,121,116,104,111,110,0,45,109,0]) + b"agency.operator_service" + bytes([0])):
                result = capture(data, resolver=resolved, show=show)
            self.assertEqual(result["runtime_identity"], "PASS")
            self.assertFalse(result["cutover_authorized"])

    def test_unsafe_resolution_rejected(self):
        data = copy.deepcopy(BASE)
        def unsafe(manifest):
            result = resolved(manifest)
            result["cutover_authorized"] = True
            return result
        with self.assertRaises(PermissionError):
            inspect(data, resolver=unsafe, show=lambda _: {})
        with self.assertRaises(PermissionError):
            capture(data, resolver=unsafe, show=lambda *_: {})


if __name__ == "__main__":
    unittest.main()
