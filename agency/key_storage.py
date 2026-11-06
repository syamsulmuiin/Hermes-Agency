"""Read-only, owner-protected keyring provisioning.

The key directory must be provisioned out of band by an administrator.
Never place private key material in the repository or agent workspace.
"""
import json
import os
import stat
from pathlib import Path
from .runtime import load_signing_key
from .keyring import RotatingCredentialKeys

def load_protected_keyring(directory,clock=None):
    directory=Path(directory)
    info=directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise PermissionError('Key directory must be private and not a symlink')
    if hasattr(os,'getuid') and info.st_uid!=os.getuid():
        raise PermissionError('Key directory owner mismatch')
    manifest=directory/'manifest.json'
    fd=os.open(manifest,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise PermissionError('Manifest must be owner-only')
        if hasattr(os,'getuid') and info.st_uid!=os.getuid():
            raise PermissionError('Manifest owner mismatch')
        raw=os.read(fd,4097)
        if len(raw)>4096:
            raise ValueError('Oversized key manifest')
    finally:
        os.close(fd)
    data=json.loads(raw)
    if not isinstance(data,dict) or set(data)!={'active','keys'}:
        raise ValueError('Invalid manifest')
    ids=data['keys']
    if (not isinstance(ids,list) or not 1<=len(ids)<=8
        or len(ids)!=len(set(ids))
        or any(not isinstance(i,str) or not i.isascii() or not i.isalnum() or len(i)>32 for i in ids)
        or data['active'] not in ids):
        raise ValueError('Invalid key ids')
    keys={name:load_signing_key(directory/(name+'.key')) for name in ids}
    return RotatingCredentialKeys(keys,data['active'],clock=clock)
