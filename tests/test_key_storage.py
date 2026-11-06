import json
import os
import tempfile
import unittest
from pathlib import Path
from agency.key_storage import load_protected_keyring

class ProtectedKeyStorageTests(unittest.TestCase):
    def test_load_and_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root)/'private'
            directory.mkdir(mode=0o700)
            (directory/'first.key').write_bytes(b'a'*32)
            (directory/'manifest.json').write_text(json.dumps({'active':'first','keys':['first']}))
            os.chmod(directory/'first.key',0o600)
            os.chmod(directory/'manifest.json',0o600)
            ring=load_protected_keyring(directory,clock=lambda:100)
            token=ring.issue('operator','approver')
            self.assertEqual(ring.verify(token,'approver'),'operator')
            os.chmod(directory/'first.key',0o644)
            with self.assertRaises(PermissionError):
                load_protected_keyring(directory)
    def test_symlink_directory_denied(self):
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root)/'private'
            directory.mkdir(mode=0o700)
            alias=Path(root)/'alias'
            alias.symlink_to(directory,target_is_directory=True)
            with self.assertRaises(PermissionError):
                load_protected_keyring(alias)
