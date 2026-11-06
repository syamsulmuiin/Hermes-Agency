import tempfile
import unittest
from pathlib import Path
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.keyring import RotatingCredentialKeys
from agency.operator_auth import LocalOperatorGate

class KeyringIntegrationTests(unittest.TestCase):
    def test_rotation_and_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SecureAgencyStore(Path(directory)/'state.sqlite',clock=lambda:100)
            keys=RotatingCredentialKeys({'first':b'a'*32},'first',clock=lambda:100)
            service=TrustedApprovalService(store,b'z'*32,clock=lambda:100,keyring=keys)
            task=store.create_task('Review','developer')
            approval=store.request_approval(task,'deploy',{},'developer')
            salt,verifier=LocalOperatorGate.provision(b'operator-secret-for-tests-only')
            gate=LocalOperatorGate(service,'reviewer',salt,verifier)
            token=gate.authenticate(b'operator-secret-for-tests-only')
            keys.rotate('second',b'b'*32)
            service.decide(approval,token,True)
            worker=service.issue_credential('worker','worker')
            lease=store.claim(task,'worker')
            grant=service.grant(approval,task,'deploy',{},worker,lease,'grant-one')
            self.assertEqual(grant['idempotency_key'],'grant-one')
            keys.retire('first')
            with self.assertRaises(PermissionError):
                service._verify(token,'approver')
            store.close()

    def test_v1_not_accepted_by_v2(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SecureAgencyStore(Path(directory)/'state.sqlite')
            legacy=TrustedApprovalService(store,b'z'*32)
            keys=RotatingCredentialKeys({'first':b'a'*32},'first')
            versioned=TrustedApprovalService(store,b'z'*32,keyring=keys)
            with self.assertRaises(PermissionError):
                versioned._verify(legacy.issue_credential('reviewer','approver'),'approver')
            store.close()
