import tempfile,threading,unittest
from pathlib import Path
from agency.security import SecureAgencyStore,AuthenticatedReviewer

PAYLOAD={'completed':['reviewed'],'output':['brief'],'notes':[],'blockers':[]}
class HardeningTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db.sqlite'
  self.store=SecureAgencyStore(self.path);self.task=self.store.create_task('Review','ceo')
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_atomic_handoff_rejects_stale_owner(self):
  self.store.handoff(self.task,'ceo','pm',PAYLOAD)
  with self.assertRaises(PermissionError):self.store.handoff(self.task,'ceo','researcher',PAYLOAD)
  self.assertEqual(self.store.db.execute('SELECT owner FROM tasks WHERE id=?',(self.task,)).fetchone()[0],'pm')
 def test_invalid_payload(self):
  with self.assertRaises(ValueError):self.store.handoff(self.task,'ceo','pm',{'completed':[1],'output':[],'notes':[],'blockers':[]})
  with self.assertRaises(ValueError):self.store.handoff(self.task,'ceo','pm',{'completed':['x'*5000],'output':[],'notes':[],'blockers':[]})
 def test_approval_role_gate(self):
  approval=self.store.request_approval(self.task,'deploy',{},'ceo')
  with self.assertRaises(PermissionError):self.store.decide_authenticated(approval,'admin',True)
  with self.assertRaises(PermissionError):self.store.decide_authenticated(approval,AuthenticatedReviewer('alice',frozenset({'auditor'})),True)
  self.store.decide_authenticated(approval,AuthenticatedReviewer('alice',frozenset({'approver'})),True)
 def test_parallel_claim(self):
  barrier=threading.Barrier(2);results=[];lock=threading.Lock()
  def worker(i):
   other=SecureAgencyStore(self.path)
   try:
    barrier.wait()
    try:other.claim(self.task,str(i));out='ok'
    except PermissionError:out='denied'
    with lock:results.append(out)
   finally:other.close()
  a=threading.Thread(target=worker,args=(1,));b=threading.Thread(target=worker,args=(2,))
  a.start();b.start();a.join(10);b.join(10)
  self.assertFalse(a.is_alive() or b.is_alive())
  self.assertEqual(sorted(results),['denied','ok'])
if __name__=='__main__':unittest.main()
