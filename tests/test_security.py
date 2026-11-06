import tempfile,unittest
from pathlib import Path
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
class SecurityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=[1000]
  self.s=SecureAgencyStore(Path(self.tmp.name)/'state.db',clock=lambda:self.now[0]);self.t=self.s.create_task('Audit','developer');self.auth=TrustedApprovalService(self.s,b'x'*32,clock=lambda:self.now[0])
 def tearDown(self): self.s.close();self.tmp.cleanup()
 def test_claim_and_fencing(self):
  a=self.s.claim(self.t,'a',10)
  with self.assertRaises(PermissionError):self.s.claim(self.t,'b')
  self.now[0]+=11;b=self.s.claim(self.t,'b',10)
  with self.assertRaises(PermissionError):self.s.transition(self.t,'developer','completed',a)
  self.s.transition(self.t,'developer','completed',b)
  with self.assertRaises(PermissionError):self.s.claim(self.t,'c')
 def test_state_guards(self):
  with self.assertRaises(PermissionError):self.s.set_status(self.t,'completed')
  with self.assertRaises(PermissionError):self.s.transition(self.t,'developer','completed')
  token=self.s.claim(self.t,'worker')
  with self.assertRaises(PermissionError):self.s.transition(self.t,'qa','completed',token)
 def test_approval_binding_and_replay(self):
  a=self.s.request_approval(self.t,'deploy',{'target':'staging'},'developer')
  with self.assertRaises(PermissionError):self.auth.decide(a,self.auth.issue_credential('developer','approver'),True)
  self.auth.decide(a,self.auth.issue_credential('human','approver'),True)
  lease=self.s.claim(self.t,'worker')
  with self.assertRaises(PermissionError):self.auth.grant(a,self.t,'deploy',{'target':'production'},self.auth.issue_credential('worker','worker'),'bad','id1')
  self.assertTrue(self.auth.grant(a,self.t,'deploy',{'target':'staging'},self.auth.issue_credential('worker','worker'),lease,'id1'))
  with self.assertRaises(PermissionError):self.auth.grant(a,self.t,'deploy',{'target':'staging'},self.auth.issue_credential('worker','worker'),lease,'id2')
 def test_expiry_and_denial(self):
  a=self.s.request_approval(self.t,'deploy',{},'developer',ttl=2)
  self.now[0]+=3
  with self.assertRaises(PermissionError):self.auth.decide(a,self.auth.issue_credential('human','approver'),True)
  b=self.s.request_approval(self.t,'deploy',{},'developer')
  self.auth.decide(b,self.auth.issue_credential('human','approver'),False)
  with self.assertRaises(PermissionError):self.auth.grant(b,self.t,'deploy',{},self.auth.issue_credential('worker','worker'),'bad','id3')
 def test_restart(self):
  a=self.s.request_approval(self.t,'deploy',{},'developer')
  self.s.close();self.s=SecureAgencyStore(Path(self.tmp.name)/'state.db',clock=lambda:self.now[0]);self.auth=TrustedApprovalService(self.s,b'x'*32,clock=lambda:self.now[0])
  self.auth.decide(a,self.auth.issue_credential('human','approver'),True);lease=self.s.claim(self.t,'worker');self.assertTrue(self.auth.grant(a,self.t,'deploy',{},self.auth.issue_credential('worker','worker'),lease,'restart'))
 def test_active_handoff_rejected(self):
  self.s.claim(self.t,'worker')
  with self.assertRaises(PermissionError):self.s.handoff(self.t,'developer','qa',{'completed':[],'output':[],'notes':[],'blockers':[]})
if __name__=='__main__':unittest.main()
