import unittest
from smartscripts.ai.versioning import VersionControl

class TestVersioning(unittest.TestCase):
    def test_version_hash_and_rollback(self):
        vc = VersionControl()
        content_v1 = {"text": "first version"}
        content_v2 = {"text": "second version"}

        hash1 = vc.save_version(content_v1)
        hash2 = vc.save_version(content_v2)

        self.assertNotEqual(hash1, hash2)
        self.assertEqual(vc.load_version(hash1), content_v1)
        self.assertEqual(vc.load_version(hash2), content_v2)

if __name__ == "__main__":
    unittest.main()

