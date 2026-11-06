import unittest
from unittest.mock import patch
from types import SimpleNamespace
from agency.sandbox import sandbox_probe

class SandboxTests(unittest.TestCase):
    def test_missing_bubblewrap_fails_closed(self):
        with patch('agency.sandbox.shutil.which',return_value=None):
            with self.assertRaises(RuntimeError):
                sandbox_probe()
    def test_no_arbitrary_execution(self):
        with patch('agency.sandbox.shutil.which',return_value='/usr/bin/bwrap'):
            with patch('agency.sandbox.subprocess.run',return_value=SimpleNamespace(returncode=0)) as run:
                result=sandbox_probe()
                args=run.call_args.args[0]
                self.assertIn('--unshare-all',args)
                self.assertIn('--clearenv',args)
                self.assertEqual(args[-1],'/bin/true')
                self.assertFalse(result['agent_tools_enabled'])
                self.assertEqual(result['resource_limits'],'rlimit-probe-only')
                self.assertEqual(run.call_args.kwargs['env'],{})
                self.assertIsNotNone(run.call_args.kwargs['preexec_fn'])
                self.assertEqual(run.call_args.kwargs['stdin'],__import__('subprocess').DEVNULL)
    def test_failed_isolation_denied(self):
        with patch('agency.sandbox.shutil.which',return_value='/usr/bin/bwrap'):
            with patch('agency.sandbox.subprocess.run',return_value=SimpleNamespace(returncode=1)):
                with self.assertRaisesRegex(RuntimeError,'exit 1'):
                    sandbox_probe()
