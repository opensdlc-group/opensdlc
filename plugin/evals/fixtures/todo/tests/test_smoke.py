import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Smoke(unittest.TestCase):
    def test_the_program_starts(self):
        result = subprocess.run([str(ROOT / "todo")], capture_output=True, text=True)
        self.assertIn("usage", result.stderr)
