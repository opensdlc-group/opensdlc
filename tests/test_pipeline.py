# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import unittest

from support import temp_project
from test_artifacts import change, edit_body

from opensdlc.globs import matches
from opensdlc.pipeline import forbidden_paths, next_actions
from opensdlc.toolset import toolset

CONFIG = {"stages": {"build": {"autoRisk": ["low"], "allowedTools": "Read,Edit,Bash(make test)"}}}
FOLDER = "changes/2026-10-claims-status"


def due(root, touched, config=CONFIG):
    return [(a.change.id, a.stage.name) for a in next_actions(root, [f"{FOLDER}/{f}" for f in touched], config)]


class OfferedTools(unittest.TestCase):
    def test_a_session_is_offered_each_tool_its_permissions_name_once(self):
        self.assertEqual(toolset("Read,Glob,Bash(git diff *),Bash(git log *),Read"), "Read,Glob,Bash")

    def test_an_edit_rule_offers_every_tool_it_governs(self):
        self.assertEqual(toolset("Read,Edit(.opensdlc/out/gate.json)"), "Read,Edit,Write")

    def test_a_comma_inside_a_rule_does_not_split_it(self):
        self.assertEqual(toolset("Edit(src/{api,web}/**), Grep"), "Edit,Write,Grep")

    def test_no_permissions_offer_no_tools(self):
        self.assertEqual(toolset(""), "")


class NextActions(unittest.TestCase):
    def test_accepted_intent_triggers_spec(self):
        root = temp_project()
        change(root, intent="accepted")
        self.assertEqual(due(root, ["intent.md"]), [("2026-10-claims-status", "spec")])

    def test_draft_intent_triggers_nothing(self):
        root = temp_project()
        change(root, intent="draft")
        self.assertEqual(due(root, ["intent.md"]), [])

    def test_existing_spec_is_not_regenerated(self):
        root = temp_project()
        change(root, intent="accepted", spec="draft")
        self.assertEqual(due(root, ["intent.md"]), [])

    def test_accepted_spec_triggers_a_draft_plan(self):
        root = temp_project()
        change(root, intent="accepted", spec="accepted")
        self.assertEqual(due(root, ["spec.md"]), [("2026-10-claims-status", "plan")])

    def test_only_the_artifact_that_changed_advances(self):
        root = temp_project()
        change(root, intent="accepted", spec="accepted")
        self.assertEqual(due(root, ["intent.md"]), [])

    def test_low_risk_accepted_plan_builds_when_enabled(self):
        root = temp_project()
        change(root, intent="accepted", spec="accepted", plan="accepted")
        actions = next_actions(root, [f"{FOLDER}/plan.md"], CONFIG)
        self.assertEqual([a.stage.name for a in actions], ["build"])
        self.assertEqual(actions[0].as_matrix_entry()["allowedTools"], "Read,Edit,Bash(make test)")

    def test_each_run_carries_the_models_its_stage_and_gate_name(self):
        root = temp_project()
        change(root, intent="accepted", spec="accepted", plan="accepted")
        config = {"stages": {**CONFIG["stages"], "gate": {"model": "claude-sonnet-5-5"}}}
        config["stages"]["build"] = {**CONFIG["stages"]["build"], "model": "haiku"}
        entry = next_actions(root, [f"{FOLDER}/plan.md"], config)[0].as_matrix_entry()
        self.assertEqual((entry["model"], entry["gateModel"]), ("haiku", "claude-sonnet-5-5"))
        self.assertEqual(next_actions(root, [f"{FOLDER}/plan.md"], CONFIG)[0].as_matrix_entry()["model"], "")

    def test_a_model_that_is_not_a_model_name_stops_the_pipeline(self):
        root = temp_project()
        change(root, intent="accepted", spec="accepted", plan="accepted")
        for model in ("haiku --dangerously-skip-permissions", "$(id)", 4):
            config = {"stages": {"build": {**CONFIG["stages"]["build"], "model": model}}}
            with self.assertRaises(ValueError):
                next_actions(root, [f"{FOLDER}/plan.md"], config)

    def test_build_is_off_without_auto_risk(self):
        root = temp_project()
        change(root, intent="accepted", spec="accepted", plan="accepted")
        self.assertEqual(due(root, ["plan.md"], {}), [])

    def test_implemented_plan_does_not_rebuild(self):
        root = temp_project()
        change(root, intent="accepted", spec="accepted", plan="implemented")
        self.assertEqual(due(root, ["plan.md"]), [])

    def test_matrix_entry_shape(self):
        root = temp_project()
        change(root, intent="accepted")
        entry = next_actions(root, [f"{FOLDER}/intent.md"], CONFIG)[0].as_matrix_entry()
        self.assertEqual(entry["change"], FOLDER)
        self.assertEqual(entry["skill"], "opensdlc:spec")
        self.assertEqual(entry["branch"], "opensdlc/2026-10-claims-status/spec")
        self.assertEqual(entry["allowedTools"], "Read,Write,Edit,Glob,Grep,Skill,Agent")
        self.assertEqual(entry["tools"], "Read,Write,Edit,Glob,Grep,Skill,Agent")
        self.assertEqual(entry["scope"], f"{FOLDER}/**")
        self.assertEqual(entry["issue"], "")

    def test_changed_intent_revises_a_reopened_spec(self):
        root = temp_project()
        c = change(root, intent="accepted", spec="accepted")
        c.reopen("spec")
        edit_body(c, "intent")
        actions = next_actions(root, [f"{FOLDER}/intent.md", f"{FOLDER}/spec.md"], CONFIG)
        self.assertEqual([(a.stage.name, a.as_matrix_entry()["mode"]) for a in actions], [("spec", "revise")])

    def test_stale_accepted_spec_is_never_rewritten_by_the_pipeline(self):
        root = temp_project()
        edit_body(change(root, intent="accepted", spec="accepted"), "intent")
        self.assertEqual(due(root, ["intent.md"]), [])

    def test_new_artifacts_are_written_not_revised(self):
        root = temp_project()
        change(root, intent="accepted")
        self.assertEqual(next_actions(root, [f"{FOLDER}/intent.md"], CONFIG)[0].as_matrix_entry()["mode"], "write")

    def test_stale_plan_never_builds(self):
        root = temp_project()
        c = change(root, intent="accepted", spec="accepted", plan="accepted")
        edit_body(c, "spec")
        self.assertEqual(due(root, ["plan.md"]), [])

    def test_paths_outside_changes_are_ignored(self):
        root = temp_project()
        change(root, intent="accepted")
        self.assertEqual(next_actions(root, ["src/changes/x/intent.md", "changes/README.md"], CONFIG), [])


class Globs(unittest.TestCase):
    def test_a_newline_cannot_slip_a_path_past_a_pattern(self):
        self.assertTrue(matches(".github/x\nsrc/a.py", [".github/**"]))
        self.assertFalse(matches("src/a.py\n", ["src/*.py"]))

    def test_forbidden_paths_ignore_case(self):
        config = {"pipeline": {"forbiddenPaths": ["**/.claude/**", "**/CLAUDE.md"]}}
        self.assertEqual(forbidden_paths([".Claude/settings.json", "pkg/claude.md", "src/a.py"], config), [".Claude/settings.json", "pkg/claude.md"])


if __name__ == "__main__":
    unittest.main()
