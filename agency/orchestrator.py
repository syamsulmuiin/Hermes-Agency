"""Deterministic, tool-free workflow coordinator.

This module never invokes an LLM, shell, network, or privileged tool.
It records completed agent stages only after an explicit caller-supplied result.
"""
import json
from .security import SecureAgencyStore

DEFAULT_ROUTE=('ceo','pm','researcher','developer','designer','qa')
FIELDS=frozenset({'completed','output','notes','blockers'})

class WorkflowCoordinator:
    def __init__(self, store: SecureAgencyStore):
        if not isinstance(store,SecureAgencyStore):
            raise TypeError('SecureAgencyStore required')
        self.store=store
        store.db.execute("""CREATE TABLE IF NOT EXISTS workflow_progress (
            task_id TEXT PRIMARY KEY REFERENCES tasks(id),
            route TEXT NOT NULL,
            stage INTEGER NOT NULL DEFAULT 0,
            finished INTEGER NOT NULL DEFAULT 0 CHECK(finished IN (0,1))
        )""")
        store.db.commit()

    def start(self,title,route=DEFAULT_ROUTE):
        if (not isinstance(route,(tuple,list)) or not route or len(route)>12
            or any(x not in DEFAULT_ROUTE for x in route)
            or len(set(route))!=len(route)):
            raise ValueError('Invalid route')
        # No external work is performed; task creation is persisted before routing.
        task_id=self.store.create_task(title,route[0])
        with self.store.db:
            self.store.db.execute(
                'INSERT INTO workflow_progress(task_id,route) VALUES(?,?)',
                (task_id,json.dumps(list(route))))
        return task_id

    def snapshot(self,task_id):
        row=self.store.db.execute(
            """SELECT t.owner,t.status,p.route,p.stage,p.finished
               FROM tasks t JOIN workflow_progress p ON p.task_id=t.id WHERE t.id=?""",
            (task_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown workflow')
        route=json.loads(row[2])
        return {'owner':row[0],'status':row[1],'route':route,
                'stage':row[3],'finished':bool(row[4])}

    def advance(self,task_id,agent,result):
        """Advance a pending stage with validated structured output.

        Caller identity must be authenticated by a future trusted server.
        This method is intentionally NOT a public network endpoint.
        """
        if not isinstance(result,dict) or set(result)!=FIELDS:
            raise ValueError('Invalid stage result')
        if not all(isinstance(v,list) and len(v)<=100 and
                   all(isinstance(x,str) and len(x)<=4096 for x in v)
                   for v in result.values()):
            raise ValueError('Invalid stage result content')
        raw=json.dumps(result,ensure_ascii=False,allow_nan=False)
        if len(raw.encode())>65536:
            raise ValueError('Oversized stage result')
        self.store._start()
        try:
            row=self.store.db.execute(
                """SELECT t.owner,t.status,p.route,p.stage,p.finished
                   FROM tasks t JOIN workflow_progress p ON p.task_id=t.id WHERE t.id=?""",
                (task_id,)).fetchone()
            if not row:
                raise ValueError('Unknown workflow')
            route=json.loads(row[2])
            if (row[4] or row[1]!='pending' or row[0]!=agent or
                row[3]>=len(route) or route[row[3]]!=agent or
                self.store.db.execute('SELECT 1 FROM task_leases WHERE task_id=?',(task_id,)).fetchone()):
                raise PermissionError('Stage cannot advance')
            if row[3]+1==len(route):
                self.store.db.execute(
                    "UPDATE tasks SET status='completed' WHERE id=?",(task_id,))
                self.store.db.execute(
                    'UPDATE workflow_progress SET stage=stage+1,finished=1 WHERE task_id=?',
                    (task_id,))
                self.store._audit(task_id,'workflow_completed',agent)
            else:
                recipient=route[row[3]+1]
                import uuid
                self.store.db.execute(
                    'INSERT INTO handoffs(id,task_id,sender,recipient,payload) VALUES(?,?,?,?,?)',
                    (str(uuid.uuid4()),task_id,agent,recipient,raw))
                self.store.db.execute(
                    'UPDATE tasks SET owner=? WHERE id=?',(recipient,task_id))
                self.store.db.execute(
                    'UPDATE workflow_progress SET stage=stage+1 WHERE task_id=?',
                    (task_id,))
                self.store._audit(task_id,'workflow_advanced',agent+'->'+recipient)
            self.store.db.commit()
            return self.snapshot(task_id)
        except BaseException:
            self.store.db.rollback()
            raise
