import unittest
from agency.keyring import RotatingCredentialKeys

class KeyringTests(unittest.TestCase):
    def setUp(self):
        self.now=[100.]
        self.keys=RotatingCredentialKeys({'first':b'a'*32},'first',clock=lambda:self.now[0])
    def test_rotation_and_retirement(self):
        old=self.keys.issue('operator','approver')
        self.keys.rotate('second',b'b'*32)
        new=self.keys.issue('operator','approver')
        self.assertEqual(self.keys.verify(old,'approver'),'operator')
        self.assertEqual(self.keys.verify(new,'approver'),'operator')
        self.keys.retire('first')
        with self.assertRaises(PermissionError):
            self.keys.verify(old,'approver')
        self.assertEqual(self.keys.verify(new,'approver'),'operator')
    def test_role_expiry_and_tamper(self):
        token=self.keys.issue('worker','worker',ttl=2)
        with self.assertRaises(PermissionError):
            self.keys.verify(token,'approver')
        with self.assertRaises(PermissionError):
            self.keys.verify(token[:-1]+'!', 'worker')
        self.now[0]+=3
        with self.assertRaises(PermissionError):
            self.keys.verify(token,'worker')
    def test_fail_closed(self):
        with self.assertRaises(PermissionError):
            self.keys.retire('first')
        with self.assertRaises(ValueError):
            self.keys.rotate('first',b'b'*32)
        with self.assertRaises(PermissionError):
            self.keys.verify('garbage','approver')
if __name__=='__main__':
    unittest.main()
