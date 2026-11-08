import unittest
from unittest.mock import Mock, patch

from agency.portable_host_capabilities import inventory


class PortableHostCapabilitiesTests(unittest.TestCase):
    @patch("agency.portable_host_capabilities.platform.system", return_value="Linux")
    def test_compatible_host_never_authorizes_sandbox_or_cutover(self, _):
        result = inventory(which=lambda name: "/usr/bin/" + name,
                           runner=lambda *a, **kw: Mock(returncode=0),
                           exists=lambda path: True)
        self.assertTrue(result["security"]["host_compatible"])
        self.assertFalse(result["security"]["sandbox_execution_authorized"])
        self.assertFalse(result["security"]["production_cutover_authorized"])
        self.assertFalse(result["sandbox"]["bubblewrap_isolation_validated"])

    @patch("agency.portable_host_capabilities.platform.system", return_value="Linux")
    def test_missing_systemd_fails_closed(self, _):
        result = inventory(which=lambda name: None,
                           exists=lambda path: True)
        self.assertFalse(result["security"]["host_compatible"])

    @patch("agency.portable_host_capabilities.platform.system", return_value="Linux")
    def test_unreachable_systemd_fails_closed(self, _):
        result = inventory(which=lambda name: "/usr/bin/systemctl",
                           runner=lambda *a, **kw: Mock(returncode=1),
                           exists=lambda path: True)
        self.assertFalse(result["security"]["host_compatible"])


if __name__ == "__main__":
    unittest.main()
