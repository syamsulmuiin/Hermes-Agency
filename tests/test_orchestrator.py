import tempfile
import unittest
from pathlib import Path
from agency.security import SecureAgencyStore
from agency.orchestrator import WorkflowCoordinator,DEFAULT_ROUTE

RESULT={'completed':['checked'],'output':['artifact'],'notes':[],'blockers':[]}

class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'state.sqlite'
        self.store=SecureAgencyStore(self.path)
        self.workflow=WorkflowCoordinator(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_six_agent_route_and_restart(self):
        task=self.workflow.start('Review implementation')
        for index,agent in enumerate(DEFAULT_ROUTE):
            if index==3:
                self.store.close()
                self.store=SecureAgencyStore(self.path)
                self.workflow=WorkflowCoordinator(self.store)
            state=self.workflow.advance(task,agent,RESULT)
            self.assertEqual(state['stage'],index+1)
        self.assertTrue(state['finished'])
        self.assertEqual(state['status'],'completed')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM handoffs WHERE task_id=?',(task,)).fetchone()[0],5)

    def test_replay_and_wrong_agent_denied(self):
        task=self.workflow.start('Review')
        with self.assertRaises(PermissionError):
            self.workflow.advance(task,'pm',RESULT)
        self.workflow.advance(task,'ceo',RESULT)
        with self.assertRaises(PermissionError):
            self.workflow.advance(task,'ceo',RESULT)
        self.assertEqual(self.workflow.snapshot(task)['stage'],1)

    def test_active_claim_blocks_advance(self):
        task=self.workflow.start('Review')
        self.store.claim(task,'worker')
        with self.assertRaises(PermissionError):
            self.workflow.advance(task,'ceo',RESULT)

    def test_invalid_result_and_route(self):
        with self.assertRaises(ValueError):
            self.workflow.start('Review',('ceo','ceo'))
        task=self.workflow.start('Review')
        with self.assertRaises(ValueError):
            self.workflow.advance(task,'ceo',{'completed':[1],'output':[],'notes':[],'blockers':[]})
        self.assertEqual(self.workflow.snapshot(task)['stage'],0)

    def test_single_stage_terminal(self):
        task=self.workflow.start('Review',('qa',))
        self.workflow.advance(task,'qa',RESULT)
        with self.assertRaises(PermissionError):
            self.workflow.advance(task,'qa',RESULT)

if __name__=='__main__':
    unittest.main()
