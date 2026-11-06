"""Versioned credential signer for trusted processes only.

This module does not authenticate users or expose a network endpoint.
"""
import base64
import hashlib
import hmac
import json
import math
import secrets
import time

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def _unb64(value):
    if not isinstance(value,str) or not value or len(value)>8192:
        raise PermissionError('Invalid token')
    try:
        return base64.b64decode(value+'='*(-len(value)%4),altchars=b'-_',validate=True)
    except (ValueError,TypeError) as exc:
        raise PermissionError('Invalid token') from exc

class RotatingCredentialKeys:
    """In-memory keyring with explicit active key and revocation by key removal."""
    def __init__(self,keys,active,clock=None):
        if not isinstance(keys,dict) or not keys or not isinstance(active,str) or active not in keys:
            raise ValueError('Invalid keyring')
        if any(not isinstance(k,str) or not k.isascii() or not k.isalnum() or len(k)>32
               or not isinstance(v,bytes) or len(v)<32 for k,v in keys.items()):
            raise ValueError('Invalid key entry')
        self._keys=dict(keys)
        self._active=active
        self._clock=clock or time.time

    def rotate(self,key_id,secret):
        if not isinstance(key_id,str) or not key_id.isascii() or not key_id.isalnum() or not 1<=len(key_id)<=32:
            raise ValueError('Invalid key id')
        if not isinstance(secret,bytes) or len(secret)<32 or key_id in self._keys:
            raise ValueError('Invalid or duplicate key')
        self._keys[key_id]=secret
        self._active=key_id

    def retire(self,key_id):
        if key_id==self._active:
            raise PermissionError('Cannot retire active key')
        if key_id not in self._keys:
            raise ValueError('Unknown key')
        del self._keys[key_id]

    def issue(self,identity,role,ttl=120):
        if not isinstance(identity,str) or not identity.strip() or len(identity)>128:
            raise ValueError('Invalid identity')
        if role not in ('approver','worker') or type(ttl) not in (int,float) or not math.isfinite(ttl) or not 1<=ttl<=3600:
            raise ValueError('Invalid role or TTL')
        claims={'sub':identity,'role':role,'exp':self._clock()+ttl,'aud':'hermes-agency-v2','nonce':secrets.token_hex(16)}
        body=_b64(json.dumps(claims,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
        prefix='v2.'+self._active+'.'+body
        signature=_b64(hmac.new(self._keys[self._active],prefix.encode(),hashlib.sha256).digest())
        return prefix+'.'+signature

    def verify(self,token,role):
        if not isinstance(token,str) or len(token)>8192:
            raise PermissionError('Invalid token')
        parts=token.split('.')
        if len(parts)!=4 or parts[0]!='v2' or parts[1] not in self._keys:
            raise PermissionError('Unknown credential key')
        prefix='.'.join(parts[:3])
        expected=hmac.new(self._keys[parts[1]],prefix.encode(),hashlib.sha256).digest()
        if not hmac.compare_digest(expected,_unb64(parts[3])):
            raise PermissionError('Invalid signature')
        try:
            claims=json.loads(_unb64(parts[2]))
        except (ValueError,UnicodeError,TypeError) as exc:
            raise PermissionError('Invalid claims') from exc
        if (not isinstance(claims,dict) or claims.get('aud')!='hermes-agency-v2'
            or claims.get('role')!=role or not isinstance(claims.get('sub'),str)
            or not claims['sub'].strip() or len(claims['sub'])>128
            or type(claims.get('exp')) not in (int,float)
            or not math.isfinite(claims['exp']) or claims['exp']<=self._clock()):
            raise PermissionError('Invalid claims')
        return claims['sub']
