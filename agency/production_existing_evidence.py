"""Read-only bindings to existing production runtime and recovery checks.

These bindings deliberately cannot provision a journal, mutate routing,
start or stop units, or release admission. No production execution CLI.
"""
import os
import stat

from .production_runtime_evidence import capture
from .production_recovery_wiring_evidence import inspect
from .fenced_startup_gate import require_recovered
from .fenced_unit_journal import _verify_store
from .production_maintenance_adapter import MaintenanceDenied


class ExistingProductionEvidence:
    def __init__(self, manifest, *, resolver, runtime_capture=capture,
                 recovery_inspect=inspect, startup_gate=require_recovered):
        self.manifest = manifest
        self.resolver = resolver
        self.runtime_capture = runtime_capture
        self.recovery_inspect = recovery_inspect
        self.startup_gate = startup_gate

    def _manifest_matches(self, resolved):
        if (resolved.get("paths") != self.manifest["paths"]
                or resolved.get("units") != self.manifest["units"]
                or resolved.get("identity_resolved") is not True
                or resolved.get("cutover_authorized") is not False):
            raise MaintenanceDenied("Deployment resolution mismatch")

    def runtime_identity(self, resolved):
        self._manifest_matches(resolved)
        report = self.runtime_capture(self.manifest, resolver=self.resolver)
        if (report.get("runtime_identity") != "PASS"
                or report.get("freeze_present") is not True
                or report.get("cutover_authorized") is not False
                or report.get("admission_behavior") != "NOT_ATTESTED"):
            raise MaintenanceDenied("Unsafe runtime evidence")
        if report.get("snapshot") != resolved["paths"]["snapshot"]:
            raise MaintenanceDenied("Candidate snapshot mismatch")
        return report

    def freeze_verified(self, resolved):
        self._manifest_matches(resolved)
        path = resolved["paths"]["freeze_marker"]
        info = os.lstat(path)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != 0 or info.st_mode & 0o022):
            raise MaintenanceDenied("Unsafe durable freeze marker")
        return True

    def recovery_wiring(self, resolved):
        self._manifest_matches(resolved)
        report = self.recovery_inspect(self.manifest, resolver=self.resolver)
        if (report.get("installed_recovery_wiring") != "PASS"
                or report.get("cutover_authorized") is not False):
            raise MaintenanceDenied("Unverified recovery wiring")
        # Static wiring is not proof of PID1 behavior.
        return report

    def journal_ready(self, resolved, journal):
        self._manifest_matches(resolved)
        if not isinstance(journal, str) or not os.path.isabs(journal):
            raise MaintenanceDenied("Explicit journal path required")
        _verify_store(journal)
        if not os.path.isfile(journal):
            raise MaintenanceDenied("Existing ownership journal required")
        if self.startup_gate(journal) is not True:
            raise MaintenanceDenied("Journal recovery gate denied")
        return True
