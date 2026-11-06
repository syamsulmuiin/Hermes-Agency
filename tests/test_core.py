import tempfile
import unittest
from pathlib import Path
from agency.core import AgencyStore, authorize

class FoundationTests(unittest.TestCase):
    def test_persistent_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'state.db'
            store = AgencyStore(path)
            task = store.create_task('Audit', 'ceo')
            store.handoff(task,'ceo','pm',{'completed':[],'output':['brief'],'notes':[],'blockers':[]})
            store.close()
            store = AgencyStore(path)
            self.assertEqual(store.db.execute('SELECT owner FROM tasks WHERE id=?',(task,)).fetchone()[0],'pm')
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0],2)
            store.close()

    def test_handoff_rejects_wrong_owner(self):
        with tempfile.TemporaryDirectory() as d:
            store = AgencyStore(Path(d)/'state.db')
            task = store.create_task('Audit','ceo')
            with self.assertRaises(PermissionError):
                store.handoff(task,'developer','qa',{'completed':[],'output':[],'notes':[],'blockers':[]})
            store.close()

    def test_fail_closed(self):
        self.assertFalse(authorize('execute_shell',True))
        self.assertFalse(authorize('read_local_metadata'))
        self.assertTrue(authorize('read_local_metadata',True))

    def test_reject_invalid_status(self):
        with tempfile.TemporaryDirectory() as d:
            store = AgencyStore(Path(d)/'state.db')
            task = store.create_task('Audit','ceo')
            with self.assertRaises(ValueError): store.set_status(task,'deployed')
            store.close()

if __name__ == '__main__': unittest.main()
