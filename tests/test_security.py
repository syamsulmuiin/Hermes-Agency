import tempfile,unittest
from pathlib import Path
from agency.security import SecureAgencyStore
class SecurityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.now=[1000]
  self.s=SecureAgencyStore(Path(self.tmp.name)/'state.db',clock=lambda:self.now[0]);self.t=self.s.create_task('Audit','developer')
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
  with self.assertRaises(PermissionError):self.s.decide(a,'developer',True)
  self.s.decide(a,'human',True)
  with self.assertRaises(PermissionError):self.s.consume(a,self.t,'deploy',{'target':'production'})
  self.assertTrue(self.s.consume(a,self.t,'deploy',{'target':'staging'}))
  with self.assertRaises(PermissionError):self.s.consume(a,self.t,'deploy',{'target':'staging'})
 def test_expiry_and_denial(self):
  a=self.s.request_approval(self.t,'deploy',{},'developer',ttl=2)
  self.now[0]+=3
  with self.assertRaises(PermissionError):self.s.decide(a,'human',True)
  b=self.s.request_approval(self.t,'deploy',{},'developer')
  self.s.decide(b,'human',False)
  with self.assertRaises(PermissionError):self.s.consume(b,self.t,'deploy',{})
 def test_restart(self):
  a=self.s.request_approval(self.t,'deploy',{},'developer')
  self.s.close();self.s=SecureAgencyStore(Path(self.tmp.name)/'state.db',clock=lambda:self.now[0])
  self.s.decide(a,'human',True);self.assertTrue(self.s.consume(a,self.t,'deploy',{}))
 def test_active_handoff_rejected(self):
  self.s.claim(self.t,'worker')
  with self.assertRaises(PermissionError):self.s.handoff(self.t,'developer','qa',{'completed':[],'output':[],'notes':[],'blockers':[]})
if __name__=='__main__':unittest.main()
