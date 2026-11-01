import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class Smoke(unittest.TestCase):
    def test_the_package_imports(self):
        import todo

        self.assertTrue(todo.__name__)
