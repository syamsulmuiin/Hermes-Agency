import tempfile
import unittest
from pathlib import Path
from agency.security import SecureAgencyStore
from agency.trusted import TrustedApprovalService
from agency.operator_auth import LocalOperatorGate

class OperatorAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=SecureAgencyStore(Path(self.tmp.name)/'state.db',clock=lambda:100)
        self.service=TrustedApprovalService(self.store,b'k'*32,clock=lambda:100)
        self.secret=b'operator-test-secret-with-entropy'
        salt,verifier=LocalOperatorGate.provision(self.secret)
        self.gate=LocalOperatorGate(self.service,'reviewer',salt,verifier)
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_correct_secret_issues_reviewer_only(self):
        token=self.gate.authenticate(self.secret)
        self.assertEqual(self.service._verify(token,'approver'),'reviewer')
        with self.assertRaises(PermissionError):
            self.service._verify(token,'worker')
    def test_incorrect_secret_denied(self):
        with self.assertRaises(PermissionError):
            self.gate.authenticate(b'another-secret-not-valid')
    def test_short_secret_denied(self):
        with self.assertRaises(PermissionError):
            self.gate.authenticate(b'bad')
    def test_invalid_provisioning_denied(self):
        with self.assertRaises(ValueError):
            LocalOperatorGate.provision(b'weak')

if __name__=='__main__':
    unittest.main()
