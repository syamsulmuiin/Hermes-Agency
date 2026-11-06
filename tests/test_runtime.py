import unittest
from agency.runtime import DryRunRuntime, load_signing_key

class RuntimeSmokeTests(unittest.TestCase):
    def test_exports(self):
        self.assertTrue(callable(load_signing_key))
        self.assertTrue(callable(DryRunRuntime))

if __name__ == '__main__':
    unittest.main()
