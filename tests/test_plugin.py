# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
import subprocess
import unittest

from support import PLUGIN, REPO

REFERENCE = re.compile(r"`([a-z][\w-]*):([a-z][\w-]*)`")
SOURCE = re.compile(r"\.(py|sh)$|(^|/)\.github/(workflows/[^/]+|actions/[^/]+/action)\.ya?ml$")
TEST_DATA = ("bench/scenarios/", "plugin/evals/")


def skill_texts():
    return {p.parent.name: p.read_text() for p in (PLUGIN / "skills").glob("*/SKILL.md")}


class Licensing(unittest.TestCase):
    def test_every_source_file_carries_the_licence_header(self):
        tracked = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True).stdout.split()
        sources = [name for name in tracked if SOURCE.search(name) and not name.startswith(TEST_DATA)]
        self.assertGreater(len(sources), 50)
        for name in sources:
            head = (REPO / name).read_text().splitlines()[:3]
            self.assertIn("# SPDX-License-Identifier: Apache-2.0", head, name)
            self.assertTrue(any(line.startswith("# Copyright ") and line.endswith(" The OpenSDLC Authors") for line in head), name)


class Release(unittest.TestCase):
    def test_the_template_pins_the_release_this_plugin_is(self):
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
        pinned = json.loads((PLUGIN / "template" / ".opensdlc" / "config.json").read_text())["plugin"]
        self.assertEqual(pinned, {"repository": "opensdlc-group/opensdlc", "ref": f"v{manifest['version']}"})

    def test_the_changelog_describes_this_release(self):
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
        self.assertIn(f"## {manifest['version']} ", (REPO / "CHANGELOG.md").read_text())


class SelfContained(unittest.TestCase):
    def test_no_plugin_dependencies(self):
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
        marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
        self.assertNotIn("dependencies", manifest)
        self.assertNotIn("allowCrossMarketplaceDependenciesOn", marketplace)

    def test_skills_only_reference_opensdlc_components_that_exist(self):
        skills = set(skill_texts())
        agents = {p.stem for p in (PLUGIN / "agents").glob("*.md")}
        for name, text in skill_texts().items():
            for namespace, target in REFERENCE.findall(text):
                self.assertEqual(namespace, "opensdlc", f"{name} references {namespace}:{target}")
                self.assertIn(target, skills | agents, f"{name} references missing opensdlc:{target}")

    def test_skill_frontmatter_names_match_folders(self):
        for name, text in skill_texts().items():
            self.assertRegex(text, rf"\A---\nname: {re.escape(name)}\n", name)

    def test_descriptions_say_in_the_third_person_what_a_skill_does_and_when_to_use_it(self):
        for name, text in skill_texts().items():
            description = re.search(r"^description: (.*)$", text, re.M).group(1)
            self.assertRegex(description, r"^[A-Z][a-z]+s\b", name)
            self.assertIn("Use ", description, name)
            self.assertLessEqual(len(description), 1024, name)

    def test_skills_that_write_a_patch_keep_headless_agents_off_paths_people_own(self):
        texts = skill_texts()
        for name in ("intent", "spec", "plan", "build", "incident", "domain"):
            self.assertIn("the pipeline refuses the whole patch", texts[name], name)


class ClaudeAiSkill(unittest.TestCase):
    ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    FOLDER = REPO / "claude-ai" / "opensdlc-intent"

    def test_frontmatter_uses_only_fields_a_claude_ai_upload_accepts(self):
        text = (self.FOLDER / "SKILL.md").read_text()
        front = re.match(r"\A---\n(.*?)\n---\n", text, re.S).group(1)
        keys = {line.split(":", 1)[0] for line in front.splitlines() if ":" in line}
        self.assertLessEqual(keys, self.ALLOWED)
        self.assertIn("name", keys)
        self.assertIn("description", keys)

    def test_template_is_the_plugin_template(self):
        self.assertEqual((self.FOLDER / "template.md").read_text(), (PLUGIN / "skills" / "intent" / "template.md").read_text())

    def test_it_does_not_depend_on_plugin_skills_or_the_cli(self):
        text = (self.FOLDER / "SKILL.md").read_text()
        self.assertNotIn("opensdlc:", text)
        self.assertNotIn("python3 -m opensdlc", text)


if __name__ == "__main__":
    unittest.main()
