"""Local operator authentication gate; not a network authentication service.

Provision operator verifier records offline. Never expose this object to agents.
"""
import hashlib
import hmac
import secrets

class LocalOperatorGate:
    """Verifies an operator secret before issuing a short-lived reviewer credential.

    This boundary must run only inside a trusted process. It does not implement
    HTTP authentication, rate limiting, MFA, or secure remote transport.
    """
    def __init__(self, approval_service, identity, salt, verifier):
        if not isinstance(identity,str) or not identity.strip() or len(identity)>128:
            raise ValueError('Invalid identity')
        if not isinstance(salt,bytes) or len(salt)<16:
            raise ValueError('Invalid salt')
        if not isinstance(verifier,bytes) or len(verifier)!=32:
            raise ValueError('Invalid verifier')
        self._service=approval_service
        self._identity=identity
        self._salt=salt
        self._verifier=verifier

    @staticmethod
    def provision(secret):
        """Run offline with a high-entropy operator secret; store verifier and salt."""
        if not isinstance(secret,bytes) or len(secret)<16:
            raise ValueError('Operator secret must be at least 16 bytes')
        salt=secrets.token_bytes(16)
        verifier=hashlib.scrypt(secret,salt=salt,n=2**14,r=8,p=1,dklen=32)
        return salt,verifier

    def authenticate(self,secret):
        if not isinstance(secret,bytes) or len(secret)<16:
            raise PermissionError('Invalid operator secret')
        candidate=hashlib.scrypt(secret,salt=self._salt,n=2**14,r=8,p=1,dklen=32)
        if not hmac.compare_digest(candidate,self._verifier):
            raise PermissionError('Invalid operator secret')
        return self._service.issue_credential(self._identity,'approver',ttl=120)
