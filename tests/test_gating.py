# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import contextlib
import io
import json
import os
import unittest
import unittest.mock
from pathlib import Path

from support import git, git_repo, temp_project
from test_artifacts import change

from opensdlc.cli import main
from opensdlc.gating import Evidence, Verdict
from opensdlc.gitio import StagedEntry
from opensdlc.pipeline import next_actions


def out(**files: str) -> Path:
    folder = temp_project() / "out"
    folder.mkdir()
    for name, text in files.items():
        (folder / name.replace("_", ".")).write_text(text)
    return folder


CONTINUE = '{"verdict": "continue", "reasons": []}'
TESTS = ("tests/**",)


def evidence(stage: str, staged: tuple[StagedEntry, ...] = (), concerns: str | None = None, planned: str | None = None, **files: str) -> Evidence:
    root = temp_project()
    c = change(root, intent="accepted", spec="accepted" if stage != "spec" else "draft", plan="accepted" if stage == "build" else "draft")
    if concerns is not None:
        c = edit_section(c, "spec", "Concerns", concerns)
    if planned is not None:
        c = edit_section(c, "plan", "Files that change", planned)
    return Evidence(stage, out(**files), c, staged, TESTS)


def edit_section(c, kind: str, heading: str, body: str):
    path = c.get(kind).path
    path.write_text(path.read_text().replace(f"## {heading}\nReal content.", f"## {heading}\n{body}"))
    return type(c).load(c.path)


def entry(path: str, status: str) -> StagedEntry:
    return StagedEntry(path, ("100644", "100644"), status)


class Verdicts(unittest.TestCase):
    def test_a_gate_that_says_continue_lets_a_draft_through(self):
        self.assertEqual(Verdict.judge(evidence("spec", gate_json=CONTINUE)), Verdict(False, ()))

    def test_an_escalation_carries_its_reasons(self):
        verdict = Verdict.judge(evidence("plan", gate_json='{"verdict": "escalate", "reasons": ["The plan names no tests."]}'))
        self.assertEqual(verdict, Verdict(True, ("The plan names no tests.",)))

    def test_anything_but_a_well_formed_verdict_escalates(self):
        for files in ({}, {"gate_json": "not json"}, {"gate_json": '{"verdict": "maybe", "reasons": []}'},
                      {"gate_json": '{"verdict": "continue"}'}, {"gate_json": '{"verdict": "escalate", "reasons": []}'}):
            self.assertTrue(Verdict.judge(evidence("spec", **files)).escalate, files)

    def test_a_build_also_needs_verification_that_passed(self):
        self.assertFalse(Verdict.judge(evidence("build", gate_json=CONTINUE, verify_md="PASS\nmake test: 0\n")).escalate)
        self.assertEqual(Verdict.judge(evidence("build", gate_json=CONTINUE)).reasons, ("Nobody verified the build.",))
        self.assertIn("FAIL", Verdict.judge(evidence("build", gate_json=CONTINUE, verify_md="FAIL\n")).reasons[0])


class CodeChecks(unittest.TestCase):
    def test_every_concern_must_say_how_it_ends(self):
        settled = "- **Order** (policy: contract): ties keep insertion order. **Resolved:** Implementation Decisions.\n- **Copy**: wording.\n  **Carried:** see Carried-forward Questions."
        self.assertFalse(Verdict.judge(evidence("spec", concerns=settled, gate_json=CONTINUE)).escalate)
        self.assertFalse(Verdict.judge(evidence("spec", concerns="None.", gate_json=CONTINUE)).escalate)
        open_ = "- **Ids**: the intent is silent on reuse. Proposed resolution: keep them."
        verdict = Verdict.judge(evidence("spec", concerns=settled + "\n" + open_, gate_json=CONTINUE))
        self.assertEqual(verdict.reasons, ("A concern says neither resolved, carried nor escalated: **Ids**: the intent is silent on reuse. Proposed resolution: keep them.",))

    def test_a_build_may_change_an_existing_test_only_where_the_plan_lists_it(self):
        staged = (entry("tests/test_store.py", "M"), entry("tests/test_old.py", "D"), entry("tests/test_new.py", "A"), entry("src/store.py", "M"))
        verdict = Verdict.judge(evidence("build", staged, planned="- `tests/test_store.py`: ids now carry a position", gate_json=CONTINUE, verify_md="PASS\n"))
        self.assertEqual(verdict.reasons, ("The build deletes tests/test_old.py, an existing test the plan does not list.",))

    def test_the_code_checks_run_only_at_the_stages_they_belong_to(self):
        staged = (entry("tests/test_old.py", "M"),)
        self.assertFalse(Verdict.judge(evidence("plan", staged, concerns="- open question", gate_json=CONTINUE)).escalate)

    def test_gate_check_reads_the_staged_patch_and_reports_for_the_pull_request(self):
        root = git_repo(temp_project({"tests": ["tests/**"]}))
        (root / "tests").mkdir()
        (root / "tests" / "test_store.py").write_text("assert True\n")
        change(root, intent="accepted", spec="accepted", plan="accepted")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "tests")
        (root / "tests" / "test_store.py").write_text("assert 1\n")
        git(root, "add", "-A")
        folder = out(gate_json=CONTINUE, verify_md="PASS\n")
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(main(["--root", str(root), "gate-check", "--stage", "build", "--change", "2026-10-claims-status", "--out", str(folder)]), 0)
        self.assertEqual(json.loads(printed.getvalue())["escalate"], True)
        self.assertIn("- The build edits tests/test_store.py, an existing test the plan does not list.", (folder / "gate-report.md").read_text())


class PluginPin(unittest.TestCase):
    def run_plugin(self, config: dict) -> tuple[int | str, str, str]:
        root = temp_project(config)
        outputs = root / "github-output"
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), unittest.mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(outputs)}):
            try:
                code = main(["--root", str(root), "plugin"])
            except SystemExit as stopped:
                code = str(stopped)
        return code, printed.getvalue(), outputs.read_text() if outputs.is_file() else ""

    def test_ci_loads_the_plugin_at_the_repository_and_ref_the_config_pins(self):
        code, printed, outputs = self.run_plugin({"plugin": {"repository": "acme/opensdlc", "ref": "v0.5.0"}})
        self.assertEqual((code, printed.strip()), (0, "acme/opensdlc@v0.5.0"))
        self.assertIn("repository=acme/opensdlc\nref=v0.5.0\npin=acme/opensdlc@v0.5.0\n", outputs)

    def test_a_missing_or_malformed_pin_stops_ci_instead_of_loading_whatever_is_latest(self):
        for config in ({}, {"plugin": {"repository": "acme/opensdlc"}}, {"plugin": {"repository": "acme/opensdlc", "ref": "v1\npin=evil"}}):
            code, _, outputs = self.run_plugin(config)
            self.assertIn("plugin.ref", str(code))
            self.assertEqual(outputs, "")


class MatrixTools(unittest.TestCase):
    CONFIG = {"stages": {"gate": {"allowedTools": "Read,Edit(.opensdlc/out/gate.json)"}, "verify": {"allowedTools": "Read,Bash(make test)"},
                         "build": {"autoRisk": ["low"]}}}

    def gate(self, touched: str, **artifacts: str) -> dict:
        root = temp_project()
        change(root, **artifacts)
        return next_actions(root, [f"changes/2026-10-claims-status/{touched}"], self.CONFIG)[0].as_matrix_entry()

    def test_a_drafting_stage_is_judged_with_the_gate_tools_alone(self):
        entry = self.gate("intent.md", intent="accepted")
        self.assertEqual((entry["gateAllowedTools"], entry["gateTools"]), ("Read,Edit(.opensdlc/out/gate.json)", "Read,Edit,Write"))

    def test_a_build_is_judged_with_the_tools_that_verify_it_as_well(self):
        entry = self.gate("plan.md", intent="accepted", spec="accepted", plan="accepted")
        self.assertEqual((entry["gateAllowedTools"], entry["gateTools"]),
                         ("Read,Edit(.opensdlc/out/gate.json),Read,Bash(make test)", "Read,Edit,Write,Bash"))


if __name__ == "__main__":
    unittest.main()
