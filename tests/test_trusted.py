import tempfile,unittest
from pathlib import Path
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService

class TrustedBoundaryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.now=[100.0]
  self.s=SecureAgencyStore(Path(self.tmp.name)/'db.sqlite',clock=lambda:self.now[0])
  self.auth=TrustedApprovalService(self.s,b's'*32,clock=lambda:self.now[0])
  self.task=self.s.create_task('Test','developer')
 def tearDown(self):
  self.s.close();self.tmp.cleanup()
 def test_legacy_bypass_closed(self):
  a=self.s.request_approval(self.task,'deploy',{},'developer')
  with self.assertRaises(PermissionError):self.s.decide(a,'reviewer',True)
  with self.assertRaises(PermissionError):self.s.consume(a,self.task,'deploy',{})
 def test_tampered_and_expired_credentials(self):
  a=self.s.request_approval(self.task,'deploy',{},'developer')
  token=self.auth.issue_credential('reviewer','approver',ttl=1)
  with self.assertRaises(PermissionError):self.auth.decide(a,token[:-2]+'XX',True)
  self.now[0]+=2
  with self.assertRaises(PermissionError):self.auth.decide(a,token,True)
 def test_wrong_role_and_worker(self):
  a=self.s.request_approval(self.task,'deploy',{},'developer')
  worker=self.auth.issue_credential('worker','worker')
  with self.assertRaises(PermissionError):self.auth.decide(a,worker,True)
  self.auth.decide(a,self.auth.issue_credential('reviewer','approver'),True)
  lease=self.s.claim(self.task,'worker')
  with self.assertRaises(PermissionError):self.auth.grant(a,self.task,'deploy',{},self.auth.issue_credential('other','worker'),lease,'one')
  with self.assertRaises(PermissionError):self.auth.grant(a,self.task,'deploy',{},worker,'wrong','one')
  self.assertEqual(self.auth.grant(a,self.task,'deploy',{},worker,lease,'one')['lease_generation'],1)
  with self.assertRaises(PermissionError):self.auth.grant(a,self.task,'deploy',{},worker,lease,'one')
 def test_expired_lease(self):
  a=self.s.request_approval(self.task,'deploy',{},'developer')
  self.auth.decide(a,self.auth.issue_credential('reviewer','approver'),True)
  lease=self.s.claim(self.task,'worker',ttl=2)
  self.now[0]+=3
  with self.assertRaises(PermissionError):self.auth.grant(a,self.task,'deploy',{},self.auth.issue_credential('worker','worker'),lease,'one')
if __name__=='__main__':unittest.main()
