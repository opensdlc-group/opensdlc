# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from support import git, git_repo, temp_project
from test_artifacts import change, edit_body, set_status

from opensdlc.cli import main
from opensdlc.evals import Agent, ClaudeCli, CommandCheck, Gate, Run, Suite, report


class FakeAgent(Agent):
    def __init__(self, edits: dict[str, str], output: str = "done"):
        self.edits = edits
        self.output = output

    def run(self, case, worktree, timeout):
        for path, content in self.edits.items():
            target = worktree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        return self.output


def eval_repo() -> Path:
    root = temp_project({})
    (root / "src").mkdir()
    (root / "src" / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_calc.py").write_text("assert True\n")
    (root / "evals" / "cases").mkdir(parents=True)
    (root / "evals" / "cases" / "add.json").write_text(json.dumps({
        "id": "fix-add",
        "prompt": "fix add",
        "checks": [
            {"type": "contains", "file": "src/calc.py", "pattern": r"return a \+ b"},
            {"type": "absent", "file": "src/calc.py", "pattern": r"a - b"},
            {"type": "unchanged", "paths": ["tests/**"]},
            {"type": "command", "run": "python3 -c 'import sys; sys.path.insert(0, \"src\"); import calc; assert calc.add(2, 2) == 4'"},
            {"type": "output", "pattern": "fixed"},
        ],
    }))
    return git_repo(root)


def commit_all(root: Path, message: str) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


class Flaky(Agent):
    def __init__(self, outcomes: list[bool]):
        self.outcomes = list(outcomes)

    def run(self, case, worktree, timeout):
        good = self.outcomes.pop(0)
        (worktree / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n" if good else "def add(a, b):\n    return a - b\n")
        return "fixed"


class Evals(unittest.TestCase):
    def test_a_correct_fix_passes_every_check(self):
        root = eval_repo()
        suite = Suite(root, FakeAgent({"src/calc.py": "def add(a, b):\n    return a + b\n"}, "fixed it"), 60)
        result = suite.run_case(suite.cases(None)[0])
        self.assertEqual(result.rate, 1.0, result.failures())

    def test_editing_tests_fails_the_unchanged_check(self):
        root = eval_repo()
        suite = Suite(root, FakeAgent({"src/calc.py": "def add(a, b):\n    return a + b\n", "tests/test_new.py": "pass\n"}, "fixed"), 60)
        result = suite.run_case(suite.cases(None)[0])
        self.assertEqual(result.rate, 0.0)
        self.assertEqual(len(result.failures()), 1)
        self.assertTrue(result.failures()[0].startswith("unchanged"))

    def test_check_commands_never_see_secrets(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        try:
            outcome = CommandCheck({"type": "command", "run": 'test -z "$ANTHROPIC_API_KEY" && test -n "$PATH"'}).evaluate(Run(Path.cwd(), "HEAD", ""))
        finally:
            del os.environ["ANTHROPIC_API_KEY"]
        self.assertTrue(outcome.passed, outcome.detail)

    def test_worktrees_are_cleaned_up(self):
        root = eval_repo()
        suite = Suite(root, FakeAgent({}), 60, repeats=2)
        suite.run_case(suite.cases(None)[0])
        self.assertEqual(len(git(root, "worktree", "list").splitlines()), 1)

    def test_agent_failure_is_a_failed_attempt_not_a_crash(self):
        class Broken(Agent):
            def run(self, case, worktree, timeout):
                raise RuntimeError("rate limited")
        root = eval_repo()
        suite = Suite(root, Broken(), 60)
        result = suite.run_case(suite.cases(None)[0])
        self.assertEqual(result.rate, 0.0)
        self.assertIn("rate limited", result.failures()[0])

    def test_repeats_measure_a_rate_not_a_coin_flip(self):
        root = eval_repo()
        suite = Suite(root, Flaky([True, False, True]), 60, repeats=3)
        result = suite.run_case(suite.cases(None)[0])
        self.assertEqual((result.passes, len(result.attempts)), (2, 3))

    def test_gate_passes_without_a_baseline_and_no_floor(self):
        root = eval_repo()
        suite = Suite(root, FakeAgent({}), 60)
        data, markdown = report([suite.run_case(suite.cases(None)[0])], Gate(), None)
        self.assertTrue(data["gate"]["ok"])
        self.assertIn("no baseline from main yet", markdown)

    def test_gate_fails_on_a_drop_against_main(self):
        root = eval_repo()
        suite = Suite(root, Flaky([True, False, False]), 60, repeats=3)
        results = [suite.run_case(suite.cases(None)[0])]
        baseline = {"passRate": 1.0, "cases": [{"id": "fix-add", "rate": 1.0}]}
        data, markdown = report(results, Gate(max_drop=0.1, case_drop=0.34), baseline)
        self.assertFalse(data["gate"]["ok"])
        self.assertIn("fell from 100% to 33%", markdown)

    def test_gate_tolerates_noise_within_the_allowed_drop(self):
        root = eval_repo()
        suite = Suite(root, Flaky([True, True, False]), 60, repeats=3)
        results = [suite.run_case(suite.cases(None)[0])]
        baseline = {"passRate": 0.9, "cases": [{"id": "fix-add", "rate": 0.9}]}
        data, _ = report(results, Gate(max_drop=0.25, case_drop=0.34), baseline)
        self.assertTrue(data["gate"]["ok"], data["gate"]["reasons"])

    def test_floor_applies_when_set(self):
        root = eval_repo()
        suite = Suite(root, FakeAgent({}), 60)
        data, _ = report([suite.run_case(suite.cases(None)[0])], Gate(floor=0.5), None)
        self.assertFalse(data["gate"]["ok"])


class PinnedClaude(unittest.TestCase):
    def test_eval_runs_load_the_plugin_ci_checked_out(self):
        reply = subprocess.CompletedProcess([], 0, json.dumps({"result": "done"}), "")
        with mock.patch("opensdlc.evals.subprocess.run", return_value=reply) as run:
            ClaudeCli(plugin=Path("/runner/temp/opensdlc-plugin/plugin")).run({"prompt": "fix it"}, Path("/work"), 60)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--plugin-dir") + 1], "/runner/temp/opensdlc-plugin/plugin")


class Commands(unittest.TestCase):
    def setUp(self):
        self.output = Path(temp_project()) / "github_output"
        os.environ["GITHUB_OUTPUT"] = str(self.output)

    def tearDown(self):
        os.environ.pop("GITHUB_OUTPUT", None)

    def outputs(self) -> dict:
        return dict(line.split("=", 1) for line in self.output.read_text().splitlines())

    def test_check_passes_clean_changes_and_fails_broken_ones(self):
        root = temp_project({})
        change(root, intent="accepted", spec="draft")
        self.assertEqual(main(["--root", str(root), "check"]), 0)
        (root / "changes" / "2026-10-claims-status" / "plan.md").write_text("no frontmatter")
        self.assertEqual(main(["--root", str(root), "check"]), 1)

    def test_check_passes_with_warnings_only(self):
        root = temp_project({})
        edit_body(change(root, intent="accepted", spec="draft"), "intent")
        self.assertEqual(main(["--root", str(root), "check"]), 0)

    def test_check_fails_a_stale_accepted_spec(self):
        root = temp_project({})
        edit_body(change(root, intent="accepted", spec="accepted"), "intent")
        self.assertEqual(main(["--root", str(root), "check"]), 1)

    def test_pin_and_reopen_commands_resolve_staleness(self):
        root = temp_project({})
        edit_body(change(root, intent="accepted", spec="accepted", plan="accepted"), "intent")
        self.assertEqual(main(["--root", str(root), "reopen", "2026-10-claims-status", "--from", "spec"]), 0)
        self.assertEqual(main(["--root", str(root), "pin", "changes/2026-10-claims-status"]), 0)
        self.assertEqual(main(["--root", str(root), "check"]), 0)

    def test_pin_rejects_an_unknown_change(self):
        with self.assertRaises(SystemExit):
            main(["--root", str(temp_project({})), "pin", "nope"])

    def test_advance_reads_the_push_from_git(self):
        root = git_repo(temp_project({}))
        base = git(root, "rev-parse", "HEAD")
        change(root, intent="accepted")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "accept intent")
        head = git(root, "rev-parse", "HEAD")
        self.assertEqual(main(["--root", str(root), "advance", "--base", base, "--head", head]), 0)
        matrix = json.loads(self.outputs()["matrix"])
        self.assertEqual([e["stage"] for e in matrix["include"]], ["spec"])

    def test_advance_handles_a_new_branch_push(self):
        root = temp_project({})
        change(root, intent="accepted")
        git_repo(root)
        main(["--root", str(root), "advance", "--base", "0" * 40, "--head", git(root, "rev-parse", "HEAD")])
        self.assertEqual(self.outputs()["count"], "1")

    def test_runbook_must_be_pre_approved_for_the_breached_tier(self):
        rollback = {"name": "rollback-deploy", "inputs": {"environment": "production-rollback"}}
        config = {"monitors": [{"name": "ci", "tiers": {"2sigma": {"action": "diagnose", "runbooks": [rollback]}, "3sigma": {"action": "propose", "runbooks": [rollback]}}}]}
        root = temp_project(config)
        (root / ".opensdlc" / "out").mkdir()
        request = root / ".opensdlc" / "out" / "runbook.json"
        request.write_text(json.dumps({"runbook": "drop-database"}))
        self.assertEqual(main(["--root", str(root), "runbook", "--monitor", "ci", "--tier", "3sigma"]), 1)
        request.write_text(json.dumps({"runbook": "rollback-deploy"}))
        self.assertEqual(main(["--root", str(root), "runbook", "--monitor", "ci", "--tier", "2sigma"]), 1)
        self.assertEqual(main(["--root", str(root), "runbook", "--monitor", "ci", "--tier", "3sigma"]), 0)
        self.assertEqual(self.outputs()["runbook"], "rollback-deploy")
        self.assertEqual(json.loads(self.outputs()["inputs"]), {"environment": "production-rollback"})
        request.write_text("[]")
        self.assertEqual(main(["--root", str(root), "runbook", "--monitor", "ci", "--tier", "3sigma"]), 1)

    def test_advance_links_newly_accepted_intents_to_their_ticket(self):
        root = git_repo(temp_project({}))
        c = change(root, intent="draft")
        intent = c.get("intent")
        intent.path.write_text(intent.with_meta(ref="#42"))
        commit_all(root, "draft")
        base = git(root, "rev-parse", "HEAD")
        set_status(type(c).load(c.path), "intent", "accepted")
        commit_all(root, "accept")
        main(["--root", str(root), "advance", "--base", base, "--head", "HEAD"])
        self.assertEqual(json.loads(self.outputs()["links"]), [{"issue": 42, "change": "2026-10-claims-status"}])

    def test_accept_command_proposes_acceptance_and_pins(self):
        root = temp_project({})
        change(root, pinned=False, intent="accepted", spec="draft")
        self.assertEqual(main(["--root", str(root), "accept", "2026-10-claims-status", "--kind", "spec"]), 0)
        self.assertEqual(main(["--root", str(root), "check"]), 0)

    def staged(self, files: dict, config: dict | None = None) -> Path:
        root = git_repo(temp_project(config or {"pipeline": {"forbiddenPaths": [".github/**", "**/CLAUDE.md", "evals/**"]}}))
        (root / "changes" / "2026-10-a").mkdir(parents=True)
        (root / "changes" / "2026-10-a" / "intent.md").write_text("x")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "existing change")
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        git(root, "add", "-A")
        return root

    def patch_check(self, root, *args):
        return main(["--root", str(root), "patch-check", *args])

    def test_patch_check_refuses_pipeline_paths_in_any_case(self):
        for path in (".github/workflows/ci.yml", "src/CLAUDE.md", "Claude.md", "evals/cases/steal.json"):
            root = self.staged({"src/a.py": "x", path: "y"})
            self.assertEqual(self.patch_check(root, "--change", "2026-10-a"), 1, path)
        self.assertEqual(self.patch_check(self.staged({"src/a.py": "x"}), "--change", "2026-10-a"), 0)

    def test_patch_check_holds_a_stage_to_its_scope_and_its_change(self):
        root = self.staged({"changes/2026-10-a/spec.md": "x", "src/a.py": "y"})
        self.assertEqual(self.patch_check(root, "--change", "2026-10-a", "--allow", "changes/2026-10-a/**"), 1)
        self.assertEqual(self.patch_check(root, "--change", "2026-10-a"), 0)
        root = self.staged({"changes/2026-10-a/spec.md": "x", "changes/2026-10-b/plan.md": "y"})
        self.assertEqual(self.patch_check(root, "--change", "2026-10-a"), 1)

    def test_a_new_change_must_be_one_new_folder_of_added_files(self):
        self.assertEqual(self.patch_check(self.staged({"changes/2026-10-new/intent.md": "x"}), "--change", "new"), 0)
        self.assertEqual(self.patch_check(self.staged({"changes/2026-10-a/spec.md": "x"}), "--change", "new"), 1)
        self.assertEqual(self.patch_check(self.staged({"changes/2026-10-b/intent.md": "x", "changes/2026-10-c/intent.md": "y"}), "--change", "new"), 1)
        self.assertEqual(self.patch_check(self.staged({"changes/Bad Id/intent.md": "x"}), "--change", "new"), 1)

    def test_patch_check_refuses_symlinks(self):
        root = self.staged({})
        (root / "src").mkdir()
        (root / "src" / "link").symlink_to("../.github")
        git(root, "add", "-A")
        self.assertEqual(self.patch_check(root, "--change", "2026-10-a"), 1)

    def test_no_runbook_request_is_a_no_op(self):
        self.assertEqual(main(["--root", str(temp_project({})), "runbook", "--monitor", "ci", "--tier", "3sigma"]), 0)


if __name__ == "__main__":
    unittest.main()
