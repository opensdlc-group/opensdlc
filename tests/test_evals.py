# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import os
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import PLUGIN

EVALS = PLUGIN / "evals"
FIXTURES = EVALS / "fixtures"
NEEDS = {"ticket": ("tickets",), "accepted_intent": ("intents",), "drafted_spec": ("intents", "specs"), "accepted_spec": ("intents", "specs"),
         "accepted_plan": ("intents", "specs", "plans"), "built": ("patches",), "pull_request": ("patches",)}
EXTENSION = {"patches": "patch"}


def cases() -> list[Path]:
    return sorted(p.parent for p in EVALS.glob("*/case.yaml"))


def steps(case: Path) -> list[list[str]]:
    return [shlex.split(line) for line in (case / "fixture.sh").read_text().splitlines()[1:] if line.strip()]


def scaffold(case: Path, into: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(case / "fixture.sh")], cwd=into, capture_output=True, text=True,
                          env={"PATH": os.environ["PATH"], "HOME": str(into.parent), "TMPDIR": str(into.parent)})


class Cases(unittest.TestCase):
    def test_every_case_names_its_folder_and_builds_its_repository_with_the_shared_scaffold(self):
        self.assertTrue(cases())
        for case in cases():
            text = (case / "case.yaml").read_text()
            self.assertIn(f"name: {case.name}\n", text)
            self.assertIn("scaffold_script: fixture.sh\n", text)
            self.assertEqual((case / "fixture.sh").read_text().splitlines()[0], 'source "$(dirname "$0")/../scaffold.sh"')

    def test_every_case_invokes_or_expects_a_skill_the_plugin_has(self):
        for case in cases():
            text = (case / "case.yaml").read_text()
            found = re.search(r"prompt: /opensdlc:([a-z-]+)", text) or re.search(r"\(\?:opensdlc:\)\?([a-z-]+)", text)
            self.assertIsNotNone(found, case.name)
            self.assertTrue((PLUGIN / "skills" / found.group(1) / "SKILL.md").is_file(), case.name)

    def test_every_fixture_a_case_names_exists(self):
        for case in cases():
            for step, *args in steps(case):
                for folder, arg in zip(NEEDS.get(step, ()), args):
                    name = f"{arg}.{EXTENSION.get(folder, 'md')}"
                    self.assertTrue((FIXTURES / folder / name).is_file(), f"{case.name}: {folder}/{name}")

    def test_every_scaffold_builds_a_repository_that_passes_check(self):
        for case in cases():
            with self.subTest(case.name), tempfile.TemporaryDirectory() as scratch:
                workspace = Path(scratch) / "cwd"
                workspace.mkdir()
                built = scaffold(case, workspace)
                self.assertEqual(built.returncode, 0, built.stderr)
                checked = subprocess.run(["python3", "-P", "-m", "opensdlc", "check"], cwd=workspace, capture_output=True, text=True,
                                         env={**os.environ, "PYTHONPATH": ".opensdlc/cli"})
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                self.assertFalse((workspace / "knowledge/policies/secure-api.md").exists())


if __name__ == "__main__":
    unittest.main()
