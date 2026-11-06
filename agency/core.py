"""Local-only task and handoff foundation. No command execution or LLM calls."""
import json
import sqlite3
import uuid
from pathlib import Path

AGENTS = frozenset({'ceo','pm','researcher','developer','designer','qa'})
STATES = frozenset({'pending','in_progress','blocked','completed','failed'})

class AgencyStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, title TEXT NOT NULL,
                owner TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS handoffs (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
                sender TEXT NOT NULL, recipient TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT REFERENCES tasks(id),
                event TEXT NOT NULL, detail TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        self.db.commit()

    def create_task(self, title, owner):
        if owner not in AGENTS or not isinstance(title, str) or not title.strip():
            raise ValueError('Invalid owner or title')
        task_id = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO tasks(id,title,owner) VALUES(?,?,?)', (task_id,title,owner))
            self._audit(task_id,'task_created',owner)
        return task_id

    def set_status(self, task_id, status):
        if status not in STATES:
            raise ValueError('Invalid task state')
        with self.db:
            row = self.db.execute('UPDATE tasks SET status=? WHERE id=? RETURNING id', (status,task_id)).fetchone()
            if row is None:
                raise ValueError('Unknown task')
            self._audit(task_id,'status_changed',status)

    def handoff(self, task_id, sender, recipient, payload):
        if sender not in AGENTS or recipient not in AGENTS or sender == recipient:
            raise ValueError('Invalid handoff agents')
        if not isinstance(payload,dict) or set(payload) != {'completed','output','notes','blockers'}:
            raise ValueError('Handoff requires completed, output, notes, blockers')
        if not all(isinstance(v, list) for v in payload.values()):
            raise ValueError('Handoff fields must be lists')
        handoff_id = str(uuid.uuid4())
        with self.db:
            row = self.db.execute('SELECT owner FROM tasks WHERE id=?',(task_id,)).fetchone()
            if row is None or row[0] != sender:
                raise PermissionError('Only current task owner may hand off')
            self.db.execute('INSERT INTO handoffs(id,task_id,sender,recipient,payload) VALUES(?,?,?,?,?)',
                            (handoff_id,task_id,sender,recipient,json.dumps(payload)))
            self.db.execute('UPDATE tasks SET owner=?,status=? WHERE id=?',(recipient,'pending',task_id))
            self._audit(task_id,'handoff',f'{sender}->{recipient}')
        return handoff_id

    def _audit(self, task_id, event, detail):
        self.db.execute('INSERT INTO audit_events(task_id,event,detail) VALUES(?,?,?)',(task_id,event,detail))

    def close(self):
        self.db.close()


def authorize(action, approved=False):
    """Fail closed: foundation has no executable actions."""
    return action == 'read_local_metadata' and approved is True
