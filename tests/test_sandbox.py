import unittest
from unittest.mock import patch
from types import SimpleNamespace
from agency.sandbox import sandbox_probe, sandbox_capabilities

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
                self.assertIn('--symlink',args)
                self.assertIn('usr/lib64',args)
                self.assertEqual(args[-1],'/bin/true')
                self.assertFalse(result['agent_tools_enabled'])
                self.assertEqual(result['resource_limits'],'rlimit-probe-only')
                self.assertEqual(run.call_args.kwargs['env'],{})
                self.assertIsNotNone(run.call_args.kwargs['preexec_fn'])
                self.assertEqual(run.call_args.kwargs['stdin'],__import__('subprocess').DEVNULL)
    def test_failed_isolation_denied(self):
        with patch('agency.sandbox.shutil.which',return_value='/usr/bin/bwrap'):
            with patch('agency.sandbox.subprocess.run',return_value=SimpleNamespace(returncode=1,stderr=b'bwrap: simulated isolation failure')):
                with self.assertRaisesRegex(RuntimeError,'exit 1'):
                    sandbox_probe()

    def test_capability_report_denied_host_fails_closed(self):
        with patch('agency.sandbox.sandbox_probe', side_effect=RuntimeError('bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted')):
            result = sandbox_capabilities()
        self.assertEqual(result['backend'], 'disabled')
        self.assertFalse(result['isolated_probe'])
        self.assertFalse(result['agent_tools_enabled'])
        self.assertEqual(result['reason'], 'host_namespace_policy_or_isolation_denied')

    def test_capability_report_success_still_disables_tools(self):
        with patch('agency.sandbox.sandbox_probe', return_value={'isolated_probe': True}):
            result = sandbox_capabilities()
        self.assertTrue(result['isolated_probe'])
        self.assertEqual(result['backend'], 'bubblewrap_probe_only')
        self.assertFalse(result['agent_tools_enabled'])

    def test_capability_report_missing_bwrap(self):
        with patch('agency.sandbox.sandbox_probe', side_effect=RuntimeError('bubblewrap not installed')):
            result = sandbox_capabilities()
        self.assertEqual(result['reason'], 'bubblewrap_missing')
        self.assertEqual(result['backend'], 'disabled')
