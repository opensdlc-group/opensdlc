# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import re
import unittest

from support import REPO, TEMPLATE

from opensdlc.toolset import toolset

WORKFLOWS = TEMPLATE / ".github" / "workflows"
JOB = re.compile(r"^  ([\w-]+):\n((?:(?:    .*)?\n)*)", re.M)
WRITE = re.compile(r"^\s+[\w-]+: write$", re.M)
AGENT = "anthropics/claude-code-action"
INTERACTIVE = {"opensdlc-claude.yml"}
ALLOWED = re.compile(r'--allowedTools "([^"]*)"')
OFFERED = re.compile(r'--tools "([^"]*)"')
MATRIX = re.compile(r"^\$\{\{ matrix\.(\w*)AllowedTools \}\}$|^\$\{\{ matrix\.allowedTools \}\}$")
INVOCATION = re.compile(r"^\s*(?:run: )?python3? (?P<flags>(?:-\w+ )*)-m opensdlc", re.M)


def split(path):
    head, body = path.read_text().split("\njobs:\n", 1)
    return head, dict(JOB.findall(body + "\n"))


def agent_jobs():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        head, jobs = split(path)
        for name, body in jobs.items():
            if AGENT in body:
                yield f"{path.name}:{name}", path.name, head, body


class AgentJobs(unittest.TestCase):
    def test_these_are_the_agent_jobs(self):
        self.assertEqual({where for where, *_ in agent_jobs()}, {
            "opensdlc-advance.yml:agent", "opensdlc-advance.yml:gate", "opensdlc-ci-triage.yml:agent", "opensdlc-claude.yml:claude",
            "opensdlc-intake.yml:agent", "opensdlc-monitor.yml:agent", "opensdlc-review.yml:reviewer",
        })

    def test_every_agent_runs_in_the_sandbox(self):
        for where, _, _, body in agent_jobs():
            self.assertIn("uses: ./.github/actions/opensdlc-sandbox", body, where)
            self.assertIn("settings: .opensdlc/ci-settings.json", body, where)

    def test_a_cd_cannot_move_the_path_rules_agents_are_held_to(self):
        for path in (TEMPLATE / ".opensdlc" / "ci-settings.json", REPO / "docs" / "managed-settings.example.json"):
            self.assertEqual(json.loads(path.read_text())["env"]["CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR"], "1", path.name)

    def test_headless_agents_hold_no_write_permission_or_credentials(self):
        for where, workflow, head, body in agent_jobs():
            if workflow in INTERACTIVE:
                continue
            self.assertIsNone(WRITE.search(head), where)
            self.assertIsNone(WRITE.search(body), where)
            self.assertIn("persist-credentials: false", body, where)
            self.assertIn("github_token: ${{ github.token }}", body, where)

    def test_every_headless_agent_is_offered_only_the_tools_its_permissions_name(self):
        for where, workflow, _, body in agent_jobs():
            if workflow in INTERACTIVE:
                continue
            allowed, offered = ALLOWED.search(body), OFFERED.search(body)
            self.assertIsNotNone(allowed, where)
            self.assertIsNotNone(offered, where)
            matrix = MATRIX.match(allowed.group(1))
            if matrix:
                self.assertEqual(offered.group(1), "${{ matrix.%s }}" % (f"{matrix.group(1)}Tools" if matrix.group(1) else "tools"), where)
            else:
                self.assertEqual(offered.group(1), toolset(allowed.group(1)), where)

    def test_every_stage_session_runs_on_the_model_its_stage_names(self):
        body = split(WORKFLOWS / "opensdlc-advance.yml")[1]
        self.assertIn("${{ matrix.model && format('--model {0}', matrix.model) || '' }}", body["agent"])
        self.assertIn("${{ matrix.gateModel && format('--model {0}', matrix.gateModel) || '' }}", body["gate"])

    def test_a_sandboxed_command_still_needs_a_rule_that_names_it(self):
        self.assertIs(json.loads((TEMPLATE / ".opensdlc" / "ci-settings.json").read_text())["sandbox"]["autoAllowBashIfSandboxed"], False)

    def test_a_private_plugin_repository_is_read_with_its_own_token_and_never_kept(self):
        action = (TEMPLATE / ".github" / "actions" / "opensdlc-plugin" / "action.yml").read_text()
        self.assertIn("token: ${{ inputs.token || github.token }}", action)
        self.assertIn("persist-credentials: false", action)
        steps = [match for workflow in WORKFLOWS.glob("*.yml")
                 for match in re.finditer(r"uses: \./\.github/actions/opensdlc-plugin\n(.*)\n(.*)\n", workflow.read_text())]
        self.assertTrue(steps)
        for step in steps:
            self.assertEqual((step.group(1).strip(), step.group(2).strip()), ("with:", "token: ${{ secrets.OPENSDLC_PLUGIN_TOKEN }}"))

    def test_pipeline_sessions_leave_out_the_skills_claude_code_bundles(self):
        self.assertIs(json.loads((TEMPLATE / ".opensdlc" / "ci-settings.json").read_text())["disableBundledSkills"], True)

    def test_nothing_from_the_workspace_runs_after_the_agent(self):
        for where, workflow, _, body in agent_jobs():
            after = body.split(AGENT, 1)[1]
            self.assertNotIn("uses: ./", after, where)
            self.assertNotIn("python -m opensdlc", after, where)
            if "opensdlc.patch" in after:
                self.assertIn("GIT_DIR: ${{ runner.temp }}/pristine.git", after, where)

    def test_agent_patches_are_checked_before_a_pull_request_opens(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            _, jobs = split(path)
            if not any(AGENT in body and "opensdlc.patch" in body for body in jobs.values()):
                continue
            for name, body in jobs.items():
                if "create-pull-request" in body:
                    self.assertIn("uses: ./.github/actions/opensdlc-apply", body, f"{path.name}:{name}")

    def test_pipeline_commits_are_authored_by_the_actions_bot(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, body in split(path)[1].items():
                if "create-pull-request" in body:
                    self.assertIn("author: github-actions[bot] <", body, f"{path.name}:{name}")


class PinnedPlugin(unittest.TestCase):
    UNPLUGGED = {"opensdlc-ci-triage.yml:agent"}

    def test_every_agent_that_uses_the_plugin_loads_the_pinned_checkout(self):
        for where, _, _, body in agent_jobs():
            self.assertNotIn("plugin_marketplaces", body, where)
            if where in self.UNPLUGGED:
                continue
            self.assertLess(body.index("uses: ./.github/actions/opensdlc-plugin"), body.index(AGENT), where)
            self.assertEqual(body.count('--plugin-dir "${{ steps.plugin.outputs.dir }}"'), body.count(AGENT), where)

    def test_the_eval_suite_runs_the_pinned_plugin(self):
        text = (WORKFLOWS / "opensdlc-evals.yml").read_text()
        self.assertNotIn("plugin marketplace add", text)
        self.assertIn('--plugin-dir "$PLUGIN_DIR"', text)

    def test_every_pull_request_the_pipeline_opens_records_the_plugin_that_wrote_it(self):
        for name in ("opensdlc-advance.yml", "opensdlc-intake.yml", "opensdlc-monitor.yml"):
            text = (WORKFLOWS / name).read_text()
            self.assertIn("OpenSDLC-Plugin: ${{ steps.pin.outputs.pin }}", text, name)
            self.assertIn('echo "Written with OpenSDLC \\`$PIN\\`."', text, name)


class TrustedJudgement(unittest.TestCase):
    def test_the_cli_never_imports_from_the_working_directory(self):
        files = list(WORKFLOWS.glob("*.yml")) + list((TEMPLATE / ".github" / "actions").glob("*/action.yml"))
        calls = [(path.name, m["flags"].split()) for path in files for m in INVOCATION.finditer(path.read_text())]
        self.assertGreaterEqual(len(calls), 10)
        for name, flags in calls:
            self.assertIn("-P", flags, name)

    def test_scoped_write_permissions_use_edit_rules(self):
        files = list(WORKFLOWS.glob("*.yml")) + [TEMPLATE / ".opensdlc" / "config.json"]
        for path in files:
            self.assertNotRegex(path.read_text(), r"\bWrite\(", f"{path.name}: Write(path) grants nothing; scope writes with Edit(path)")

    def test_every_applied_patch_is_held_to_a_change(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, body in split(path)[1].items():
                if "opensdlc-apply" in body:
                    self.assertRegex(body, r"\n\s+change: \S+", f"{path.name}:{name}")

    def test_checks_and_approvals_judge_with_the_base_branch_rules(self):
        for name in ("opensdlc-checks.yml", "opensdlc-approvals.yml"):
            text = (WORKFLOWS / name).read_text()
            self.assertIn("pull_request_target", text, name)
            for job, body in split(WORKFLOWS / name)[1].items():
                self.assertIn('git checkout "$BASE" -- .opensdlc', body, f"{name}:{job}")
                self.assertIn("persist-credentials: false", body, f"{name}:{job}")


if __name__ == "__main__":
    unittest.main()
