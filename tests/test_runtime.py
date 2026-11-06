import os
import tempfile
import unittest
from pathlib import Path
from agency.security import SecureAgencyStore
from agency.runtime import DryRunRuntime, load_signing_key

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)
        self.now=[100.]
        self.store=SecureAgencyStore(self.path/'state.db',clock=lambda:self.now[0])
        self.runtime=DryRunRuntime(self.store,b'k'*32,clock=lambda:self.now[0])
        self.task=self.store.create_task('Review','developer')
        approval=self.store.request_approval(self.task,'write_files',{'path':'report.txt'},'developer')
        self.runtime.auth.decide(approval,self.runtime.auth.issue_credential('reviewer','approver'),True)
        self.lease=self.store.claim(self.task,'worker',ttl=20)
        self.worker=self.runtime.auth.issue_credential('worker','worker')
        self.runtime.auth.grant(approval,self.task,'write_files',{'path':'report.txt'},self.worker,self.lease,'key-1')
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_dry_run_has_no_external_effect(self):
        result=self.runtime.inspect(self.task,'write_files',{'path':'report.txt'},self.worker,self.lease,'key-1')
        self.assertTrue(result['allowed'])
        self.assertFalse(result['executed'])
        self.assertFalse((self.path/'report.txt').exists())
    def test_action_and_worker_mismatch(self):
        with self.assertRaises(PermissionError):
            self.runtime.inspect(self.task,'deploy',{'path':'report.txt'},self.worker,self.lease,'key-1')
        other=self.runtime.auth.issue_credential('other','worker')
        with self.assertRaises(PermissionError):
            self.runtime.inspect(self.task,'write_files',{'path':'report.txt'},other,self.lease,'key-1')
    def test_stale_lease(self):
        self.now[0]+=21
        with self.assertRaises(PermissionError):
            self.runtime.inspect(self.task,'write_files',{'path':'report.txt'},self.worker,self.lease,'key-1')
    def test_owner_only_key(self):
        key=self.path/'signing.key'
        key.write_bytes(b'k'*32)
        os.chmod(key,0o600)
        self.assertEqual(load_signing_key(key),b'k'*32)
        os.chmod(key,0o644)
        with self.assertRaises(PermissionError):
            load_signing_key(key)

if __name__=='__main__':
    unittest.main()
