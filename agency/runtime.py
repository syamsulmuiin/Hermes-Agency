"""Fail-closed local runtime boundary. No shell/network/deployment execution.

Trusted operators supply the key through a protected file; agents cannot mint
credentials through this interface. Execution is intentionally a dry-run.
"""
import hmac
import os
import stat
from pathlib import Path
from .trusted import TrustedApprovalService
from .security import fingerprint

def load_signing_key(path):
    """Read a pre-provisioned 32+ byte key; reject symlinks and weak permissions."""
    path=Path(path)
    flags=os.O_RDONLY
    if not hasattr(os,'O_NOFOLLOW'):
        raise RuntimeError('Symlink-safe key loading unsupported')
    flags|=os.O_NOFOLLOW
    fd=os.open(path,flags)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise PermissionError('Key file must be regular and owner-only')
        if hasattr(os,'getuid') and info.st_uid!=os.getuid():
            raise PermissionError('Key file owner mismatch')
        raw=os.read(fd,4097)
        if len(raw)<32 or len(raw)>4096:
            raise ValueError('Invalid key length')
        return raw
    finally:
        os.close(fd)

class DryRunRuntime:
    """Trusted, side-effect-free validation of previously reserved grants.

    This is NOT a sandbox or tool executor. Nothing is run or written outside
    the SQLite database. Repeated inspection does not consume a second grant.
    """
    def __init__(self,store,secret,clock=None):
        self.store=store
        self.auth=TrustedApprovalService(store,secret,clock=clock)

    def inspect(self,task_id,action,params,credential,lease_token,idempotency_key):
        worker=self.auth._verify(credential,'worker')
        digest=fingerprint(params)
        if not isinstance(lease_token,str) or not isinstance(idempotency_key,str):
            raise PermissionError('Missing lease or grant')
        self.store._start()
        try:
            grant=self.store.db.execute(
                'SELECT task_id,action,params_hash,worker,lease_generation FROM execution_grants WHERE idempotency_key=?',
                (idempotency_key,)).fetchone()
            lease=self.store.db.execute(
                'SELECT worker,token,expires_at,generation FROM task_leases WHERE task_id=?',
                (task_id,)).fetchone()
            task=self.store.db.execute('SELECT status FROM tasks WHERE id=?',(task_id,)).fetchone()
            if (not grant or grant[:4]!=(task_id,action,digest,worker)
                or not lease or lease[0]!=worker or not hmac.compare_digest(lease[1],lease_token)
                or lease[2]<=self.auth.clock() or grant[4]!=lease[3]
                or not task or task[0]!='in_progress'):
                raise PermissionError('Stale or mismatched execution grant')
            self.store.db.commit()
            return {'allowed':True,'executed':False,'action':action,'idempotency_key':idempotency_key}
        except BaseException:
            self.store.db.rollback()
            raise
