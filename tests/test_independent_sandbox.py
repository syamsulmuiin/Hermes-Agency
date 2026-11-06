import unittest
from unittest.mock import patch

from agency.independent_sandbox import discover_backends, require_isolated_backend


class IndependentSandboxTests(unittest.TestCase):
    def test_no_docker_cli_is_disabled(self):
        with patch("agency.independent_sandbox.shutil.which", return_value=None):
            report = discover_backends()
        self.assertEqual(report["backend"], "disabled")
        self.assertFalse(report["agent_tools_enabled"])
        self.assertFalse(report["candidates"]["docker"]["validated"])

    def test_docker_cli_does_not_enable_tools(self):
        with patch("agency.independent_sandbox.shutil.which", return_value="/usr/bin/docker"):
            report = discover_backends()
        self.assertTrue(report["candidates"]["docker"]["cli_installed"])
        self.assertFalse(report["isolated_probe"])
        self.assertFalse(report["agent_tools_enabled"])

    def test_denies_execution_without_validated_backend(self):
        with self.assertRaisesRegex(RuntimeError, "execution denied"):
            require_isolated_backend()
