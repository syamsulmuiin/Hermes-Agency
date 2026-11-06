import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agency.systemd_acceptance import verify_systemd_isolation
from agency.trusted_job_admission import TrustedJobAdmission
from agency.trusted import TrustedApprovalService


class SystemdAcceptanceTests(unittest.TestCase):
    def test_non_root_denied(self):
        with patch("agency.systemd_acceptance.os.geteuid", return_value=995):
            with self.assertRaises(PermissionError):
                verify_systemd_isolation()

    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            verify_systemd_isolation(0)

    @patch("agency.systemd_acceptance.os.geteuid", return_value=0)
    @patch("agency.systemd_acceptance.shutil.which", return_value="/usr/bin/systemd-run")
    @patch("agency.systemd_acceptance.subprocess.run")
    def test_all_isolation_checks_required(self, run, which, uid):
        checks = dict(non_root=True, host_shadow_unreadable=True,
                      root_home_inaccessible=True, usr_not_writable=True,
                      inet_socket_denied=True)
        import json
        run.return_value = SimpleNamespace(returncode=0,
                                            stdout=json.dumps(checks).encode(), stderr=b"")
        report = verify_systemd_isolation()
        self.assertTrue(report["accepted"])
        self.assertFalse(report["agent_tools_enabled"])
        argv = run.call_args.args[0]
        self.assertIn("PrivateNetwork=yes", argv)
        self.assertIn("ProtectSystem=strict", argv)

    @patch("agency.systemd_acceptance.os.geteuid", return_value=0)
    @patch("agency.systemd_acceptance.shutil.which", return_value="/usr/bin/systemd-run")
    @patch("agency.systemd_acceptance.subprocess.run")
    def test_one_failed_check_denies(self, run, which, uid):
        run.return_value = SimpleNamespace(returncode=0, stderr=b"",
            stdout=b'{"non_root":true,"host_shadow_unreadable":true,"root_home_inaccessible":true,"usr_not_writable":true,"inet_socket_denied":false}')
        with self.assertRaises(PermissionError):
            verify_systemd_isolation()

    def test_admission_rejects_wrong_service(self):
        with self.assertRaises(TypeError):
            TrustedJobAdmission(None)

    def test_admission_cannot_execute(self):
        with patch.object(TrustedApprovalService, "_verify", return_value="Developer"):
            service = object.__new__(TrustedApprovalService)
            admission = TrustedJobAdmission(service)
            with self.assertRaises(PermissionError):
                admission.admit("Developer", "noop", "credential")
            with self.assertRaises(PermissionError):
                admission.admit("Developer", "/bin/sh", "credential", approved=True)
            with self.assertRaises(PermissionError):
                admission.admit("QA", "noop", "credential", approved=True)
            result = admission.admit("Developer", "noop", "credential", approved=True)
            self.assertEqual(result["status"], "admitted_not_executed")
            self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
