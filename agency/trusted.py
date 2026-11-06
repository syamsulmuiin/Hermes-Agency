"""Trusted in-process boundary for approval decisions; no tool execution.

The signing key MUST be held by a trusted server process and never exposed to agents.
"""
import base64
import binascii
import hashlib
import hmac
import json
import math
import secrets
import time
from .security import fingerprint, ACTIONS

def _encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')

def _decode(value):
    if not isinstance(value,str) or len(value)>8192:
        raise PermissionError('Invalid credential')
    return base64.urlsafe_b64decode(value + '='*(-len(value)%4))

class TrustedApprovalService:
    def __init__(self,store,secret,clock=None):
        if not isinstance(secret,bytes) or len(secret)<32:
            raise ValueError('A private signing key of at least 32 bytes is required')
        self.store=store
        self._secret=secret
        self.clock=clock or time.time
        self.store.db.execute('''CREATE TABLE IF NOT EXISTS execution_grants(
            idempotency_key TEXT PRIMARY KEY,
            approval_id TEXT NOT NULL UNIQUE REFERENCES approvals(id),
            task_id TEXT NOT NULL REFERENCES tasks(id),
            action TEXT NOT NULL,
            params_hash TEXT NOT NULL,
            worker TEXT NOT NULL,
            lease_generation INTEGER NOT NULL,
            created_at REAL NOT NULL
        )''')
        self.store.db.commit()

    def issue_credential(self,identity,role,ttl=300):
        """Call ONLY from trusted authentication infrastructure, never agent inputs."""
        if not isinstance(identity,str) or not identity.strip() or len(identity)>128:
            raise ValueError('Invalid identity')
        if role not in ('approver','worker') or type(ttl) not in (int,float) or not 1<=ttl<=3600:
            raise ValueError('Invalid role or lifetime')
        body={'sub':identity,'role':role,'exp':self.clock()+ttl,'nonce':secrets.token_hex(16),'aud':'hermes-agency-v1'}
        raw=json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        signature=hmac.new(self._secret,raw,hashlib.sha256).digest()
        return _encode(raw)+'.'+_encode(signature)

    def _verify(self,credential,role):
        try:
            body,signature=credential.split('.')
            raw=_decode(body)
            if not hmac.compare_digest(hmac.new(self._secret,raw,hashlib.sha256).digest(),_decode(signature)):
                raise PermissionError('Bad signature')
            claims=json.loads(raw)
            if (not isinstance(claims,dict) or claims.get('aud')!='hermes-agency-v1'
                or claims.get('role')!=role or not isinstance(claims.get('sub'),str)
                or not claims['sub'] or len(claims['sub'])>128
                or not isinstance(claims.get('exp'),(int,float))
                or not math.isfinite(claims['exp']) or claims['exp']<=self.clock()):
                raise PermissionError('Invalid credential claims')
            return claims['sub']
        except (ValueError,TypeError,KeyError,UnicodeError,AttributeError,binascii.Error) as exc:
            raise PermissionError('Invalid credential') from exc

    def decide(self,approval,credential,allow):
        reviewer=self._verify(credential,'approver')
        return self.store._decide_internal(approval,reviewer,allow)

    def grant(self,approval,task_id,action,params,credential,lease_token,idempotency_key):
        """Reserve a single-use grant; caller must still enforce tool-side fencing.

        A grant is not permission to execute commands in this prototype.
        """
        worker=self._verify(credential,'worker')
        if action not in ACTIONS or not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=128:
            raise ValueError('Invalid action or idempotency key')
        digest=fingerprint(params)
        self.store._start()
        try:
            row=self.store.db.execute(
                'SELECT task_id,action,params_hash,status,expires_at FROM approvals WHERE id=?',(approval,)).fetchone()
            lease=self.store.db.execute(
                'SELECT worker,token,expires_at,generation FROM task_leases WHERE task_id=?',(task_id,)).fetchone()
            task=self.store.db.execute('SELECT status FROM tasks WHERE id=?',(task_id,)).fetchone()
            if (not row or row[:3]!=(task_id,action,digest) or row[3]!='approved'
                or row[4]<=self.clock() or not lease or lease[0]!=worker
                or not isinstance(lease_token,str)
                or not hmac.compare_digest(lease[1],lease_token)
                or lease[2]<=self.clock() or not task or task[0]!='in_progress'):
                raise PermissionError('Grant forbidden')
            self.store.db.execute(
                'INSERT INTO execution_grants VALUES(?,?,?,?,?,?,?,?)',
                (idempotency_key,approval,task_id,action,digest,worker,lease[3],self.clock()))
            self.store.db.execute("UPDATE approvals SET status='consumed' WHERE id=?",(approval,))
            self.store._audit(task_id,'grant_reserved',action)
            self.store.db.commit()
            return {'idempotency_key':idempotency_key,'lease_generation':lease[3]}
        except BaseException:
            self.store.db.rollback()
            raise
