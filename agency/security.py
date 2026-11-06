"""Fail-closed SQLite scheduling and approval primitives. No tool execution."""
import hashlib, json, secrets, time
from .core import AgencyStore, AGENTS

TRANSITIONS={'pending':{'blocked','failed'},'in_progress':{'completed','blocked','failed'},'blocked':{'pending','failed'},'completed':set(),'failed':set()}
ACTIONS=frozenset({'execute_shell','write_files','deploy','network_access','access_secrets'})
def fingerprint(params):
    if not isinstance(params,dict): raise ValueError('Expected parameter object')
    raw=json.dumps(params,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>65536: raise ValueError('Oversized parameters')
    return hashlib.sha256(raw).hexdigest()

class SecureAgencyStore(AgencyStore):
    def __init__(self,path,clock=None):
        super().__init__(path)
        self.clock=clock or time.time
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS task_leases(task_id TEXT PRIMARY KEY REFERENCES tasks(id),worker TEXT NOT NULL,token TEXT NOT NULL UNIQUE,expires_at REAL NOT NULL,generation INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,task_id TEXT NOT NULL REFERENCES tasks(id),action TEXT NOT NULL,params_hash TEXT NOT NULL,requested_by TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('pending','approved','denied','consumed')),reviewer TEXT,expires_at REAL NOT NULL);
        """)
    def _start(self): self.db.execute('BEGIN IMMEDIATE')
    def set_status(self,task_id,status):
        raise PermissionError('Use claim() or transition()')
    def claim(self,task_id,worker,ttl=60):
        if not isinstance(worker,str) or not worker.strip() or len(worker)>128 or not isinstance(ttl,(int,float)) or not 1<=ttl<=3600: raise ValueError('Invalid lease')
        self._start()
        try:
            now=self.clock()
            state=self.db.execute('SELECT status FROM tasks WHERE id=?',(task_id,)).fetchone()
            lease=self.db.execute('SELECT expires_at,generation FROM task_leases WHERE task_id=?',(task_id,)).fetchone()
            if not state: raise ValueError('Unknown task')
            if state[0]=='pending' and not lease: generation=1
            elif state[0]=='in_progress' and lease and lease[0]<=now: generation=lease[1]+1
            else: raise PermissionError('Already claimed or terminal')
            token=secrets.token_urlsafe(32)
            self.db.execute('INSERT OR REPLACE INTO task_leases VALUES(?,?,?,?,?)',(task_id,worker,token,now+ttl,generation))
            self.db.execute("UPDATE tasks SET status='in_progress' WHERE id=?",(task_id,))
            self._audit(task_id,'claimed',str(generation))
            self.db.commit()
            return token
        except BaseException:
            self.db.rollback(); raise
    def transition(self,task_id,owner,target,token=None):
        if owner not in AGENTS or target not in TRANSITIONS: raise ValueError('Invalid owner/state')
        self._start()
        try:
            row=self.db.execute('SELECT owner,status FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row or row[0]!=owner or target not in TRANSITIONS[row[1]]: raise PermissionError('Forbidden transition')
            if row[1]=='in_progress':
                lease=self.db.execute('SELECT token,expires_at FROM task_leases WHERE task_id=?',(task_id,)).fetchone()
                if not lease or lease[0]!=token or lease[1]<=self.clock(): raise PermissionError('Missing/expired fencing token')
            self.db.execute('UPDATE tasks SET status=? WHERE id=?',(target,task_id))
            self.db.execute('DELETE FROM task_leases WHERE task_id=?',(task_id,))
            self._audit(task_id,'transition',row[1]+'->'+target)
            self.db.commit()
        except BaseException:
            self.db.rollback(); raise
    def request_approval(self,task_id,action,params,requester,ttl=300):
        if action not in ACTIONS or requester not in AGENTS or not isinstance(ttl,(int,float)) or not 1<=ttl<=86400: raise ValueError('Invalid request')
        h=fingerprint(params)
        self._start()
        try:
            row=self.db.execute('SELECT owner FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row or row[0]!=requester: raise PermissionError('Not task owner')
            approval=secrets.token_urlsafe(24)
            self.db.execute("INSERT INTO approvals(id,task_id,action,params_hash,requested_by,status,expires_at) VALUES(?,?,?,?,?,'pending',?)",(approval,task_id,action,h,requester,self.clock()+ttl))
            self._audit(task_id,'approval_requested',action)
            self.db.commit(); return approval
        except BaseException:
            self.db.rollback(); raise
    def decide(self,approval,reviewer,allow):
        # reviewer must be authenticated by a future trusted API boundary.
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>128 or type(allow)!=bool: raise ValueError('Invalid decision')
        self._start()
        try:
            row=self.db.execute('SELECT task_id,status,expires_at,requested_by FROM approvals WHERE id=?',(approval,)).fetchone()
            if not row or row[1]!='pending' or row[2]<=self.clock() or reviewer==row[3]: raise PermissionError('Decision forbidden')
            self.db.execute('UPDATE approvals SET status=?,reviewer=? WHERE id=?',('approved' if allow else 'denied',reviewer,approval))
            self._audit(row[0],'approval_decided','approved' if allow else 'denied')
            self.db.commit()
        except BaseException:
            self.db.rollback(); raise
    def consume(self,approval,task_id,action,params):
        h=fingerprint(params)
        self._start()
        try:
            row=self.db.execute('SELECT task_id,action,params_hash,status,expires_at FROM approvals WHERE id=?',(approval,)).fetchone()
            if not row or row[:3]!=(task_id,action,h) or row[3]!='approved' or row[4]<=self.clock(): raise PermissionError('Approval invalid')
            self.db.execute("UPDATE approvals SET status='consumed' WHERE id=?",(approval,))
            self._audit(task_id,'approval_consumed',action)
            self.db.commit(); return True
        except BaseException:
            self.db.rollback(); raise
    def handoff(self,task_id,sender,recipient,payload):
        row=self.db.execute('SELECT status FROM tasks WHERE id=?',(task_id,)).fetchone()
        if not row or row[0] not in ('pending','blocked'): raise PermissionError('Active task cannot hand off')
        return super().handoff(task_id,sender,recipient,payload)
